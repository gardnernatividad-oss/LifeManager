import uuid

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    NotificationDelivery,
    NotificationJob,
    PushSubscription,
    ReminderPreference,
    User,
)
from app.models.enums import (
    DeliveryStatus,
    NotificationJobStatus,
    NotificationType,
    ReminderType,
)
from app.services.v2_home import get_home_summary
from app.services.v2_notifications import NOTIFICATION_TYPES, _fernet, job_is_still_eligible, scheduled_instant
from app.services.v2_review import get_global_review


class PushResult(StrEnum):
    DELIVERED = "DELIVERED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


class PushTransport(Protocol):
    def send(self, *, endpoint: str, p256dh: str, auth: str, payload: dict[str, str]) -> PushResult: ...


@dataclass(frozen=True)
class NotificationContent:
    title: str
    body: str
    destination: str


def _compact(parts: list[tuple[int, str, str]]) -> str:
    return " · ".join(f"{count} {singular if count == 1 else plural}" for count, singular, plural in parts)


def compose_daily_summary(db: Session, *, user: User, now: datetime) -> NotificationContent:
    home = get_home_summary(db, user_id=user.id, timezone_name=user.timezone, now=now)
    tasks, pending, stages, activities = home.today
    if tasks + pending + stages + activities + len(home.attention) == 0:
        body = "No tienes elementos pendientes para hoy."
    else:
        body = _compact([
            (tasks, "tarea", "tareas"),
            (pending, "pendiente", "pendientes"),
            (stages, "etapa", "etapas"),
            (activities, "actividad", "actividades"),
            (len(home.attention), "atrasado", "atrasados"),
        ])
    return NotificationContent("Resumen de hoy", body, "HOME")


def compose_daily_review(db: Session, *, user: User, now: datetime) -> NotificationContent | None:
    local_date = now.astimezone(ZoneInfo(user.timezone)).date()
    review = get_global_review(db, user_id=user.id, local_date=local_date)
    counts = (len(review.tasks), len(review.pending_items), len(review.project_stages))
    if sum(counts) == 0:
        return None
    return NotificationContent(
        "Revisión diaria",
        _compact([
            (counts[0], "tarea", "tareas"),
            (counts[1], "pendiente", "pendientes"),
            (counts[2], "etapa por revisar", "etapas por revisar"),
        ]),
        "REVIEW",
    )


def _current_schedule_matches(db: Session, *, job: NotificationJob, user: User) -> bool:
    preference_type = next((key for key, value in NOTIFICATION_TYPES.items() if value == job.notification_type), None)
    if preference_type not in (ReminderType.DAILY_SUMMARY, ReminderType.DAILY_REVIEW):
        return False
    preference = db.scalar(select(ReminderPreference).where(
        ReminderPreference.user_id == user.id,
        ReminderPreference.reminder_type == preference_type,
    ))
    from app.services.v2_notifications import DEFAULTS
    local_time = preference.local_time if preference is not None else DEFAULTS[preference_type][1]
    zone = ZoneInfo(user.timezone)
    local_date = job.scheduled_for.astimezone(zone).date()
    return scheduled_instant(local_date, local_time, zone) == job.scheduled_for


def _notification_for_job(db: Session, *, job: NotificationJob, content: NotificationContent) -> Notification:
    notification_type = job.notification_type.value if isinstance(job.notification_type, NotificationType) else job.notification_type
    if job.notification_id is not None:
        notification = db.get(Notification, job.notification_id)
        if notification is not None:
            notification.title = content.title
            notification.body = content.body
            notification.deep_link = "/inicio" if content.destination == "HOME" else "/revision"
            notification.payload = {"type": notification_type, "destination": content.destination}
            return notification
    notification = Notification(
        recipient_user_id=job.user_id,
        notification_type=job.notification_type,
        title=content.title,
        body=content.body,
        deep_link="/inicio" if content.destination == "HOME" else "/revision",
        payload={"type": notification_type, "destination": content.destination},
        dedup_key=job.dedup_key,
    )
    db.add(notification)
    db.flush()
    job.notification_id = notification.id
    return notification


def deliver_job(
    db: Session,
    *,
    job_id: uuid.UUID,
    now: datetime,
    transport: PushTransport,
) -> NotificationJob | None:
    job = db.scalar(select(NotificationJob).where(
        NotificationJob.id == job_id,
        NotificationJob.status.in_((NotificationJobStatus.PENDING, NotificationJobStatus.FAILED)),
        NotificationJob.scheduled_for <= now,
    ).with_for_update(skip_locked=True))
    if job is None:
        return None
    job.status = NotificationJobStatus.PROCESSING
    job.attempted_at = now
    user = db.get(User, job.user_id)
    if user is None or not job_is_still_eligible(db, job=job) or not _current_schedule_matches(db, job=job, user=user):
        job.status = NotificationJobStatus.CANCELLED
        db.flush()
        return job

    if job.notification_type == NotificationType.DAILY_SUMMARY_REMINDER:
        content = compose_daily_summary(db, user=user, now=now)
    elif job.notification_type == NotificationType.DAILY_REVIEW_REMINDER:
        content = compose_daily_review(db, user=user, now=now)
        if content is None:
            job.status = NotificationJobStatus.CANCELLED
            db.flush()
            return job
    else:
        job.status = NotificationJobStatus.CANCELLED
        db.flush()
        return job

    notification = _notification_for_job(db, job=job, content=content)
    subscriptions = list(db.scalars(select(PushSubscription).where(
        PushSubscription.user_id == user.id,
        PushSubscription.is_active.is_(True),
    ).order_by(PushSubscription.id)).all())
    if not subscriptions:
        job.status = NotificationJobStatus.CANCELLED
        db.flush()
        return job

    existing = {row.push_subscription_id: row for row in db.scalars(select(NotificationDelivery).where(
        NotificationDelivery.notification_id == notification.id,
    )).all()}
    cipher = _fernet()
    transient = False
    delivered = False
    for subscription in subscriptions:
        delivery = existing.get(subscription.id)
        if delivery is not None and delivery.status == DeliveryStatus.DELIVERED:
            delivered = True
            continue
        if delivery is None:
            delivery = NotificationDelivery(notification_id=notification.id, push_subscription_id=subscription.id, attempt_count=0)
            db.add(delivery)
        delivery.attempt_count += 1
        notification_type = job.notification_type.value if isinstance(job.notification_type, NotificationType) else job.notification_type
        payload = {"type": notification_type, "title": content.title, "body": content.body, "destination": content.destination}
        try:
            result = transport.send(
                endpoint=cipher.decrypt(subscription.endpoint_ciphertext).decode(),
                p256dh=cipher.decrypt(subscription.p256dh_ciphertext).decode(),
                auth=cipher.decrypt(subscription.auth_ciphertext).decode(),
                payload=payload,
            )
        except Exception:
            result = PushResult.TRANSIENT_FAILURE
        if result == PushResult.DELIVERED:
            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivered_at = now
            delivery.next_attempt_at = None
            delivery.last_error_code = None
            subscription.last_success_at = now
            delivered = True
        elif result == PushResult.PERMANENT_FAILURE:
            delivery.status = DeliveryStatus.CANCELLED
            delivery.next_attempt_at = None
            delivery.last_error_code = "PERMANENT"
            subscription.is_active = False
            subscription.invalidated_at = now
        else:
            delivery.status = DeliveryStatus.PENDING
            delivery.next_attempt_at = now
            delivery.last_error_code = "TRANSIENT"
            transient = True
    if transient:
        job.status = NotificationJobStatus.FAILED
    elif delivered:
        job.status = NotificationJobStatus.SENT
        job.sent_at = now
    else:
        job.status = NotificationJobStatus.CANCELLED
    db.flush()
    return job


def claim_due_job_ids(db: Session, *, now: datetime, limit: int = 100) -> list[uuid.UUID]:
    return list(db.scalars(
        select(NotificationJob.id)
        .where(
            NotificationJob.status.in_((NotificationJobStatus.PENDING, NotificationJobStatus.FAILED)),
            NotificationJob.scheduled_for <= now,
        )
        .order_by(NotificationJob.scheduled_for, NotificationJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all())
