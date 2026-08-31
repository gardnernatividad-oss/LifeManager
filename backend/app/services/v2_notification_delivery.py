import uuid

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    NotificationDelivery,
    NotificationJob,
    PendingItem,
    Project,
    ProjectStage,
    PushSubscription,
    ReminderPreference,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.enums import (
    DeliveryStatus,
    MembershipStatus,
    NotificationJobStatus,
    NotificationType,
    ReminderType,
    WorkspaceLifecycle,
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


def pending_weekly_counts(db: Session, *, user: User, now: datetime) -> tuple[int, int]:
    today = now.astimezone(ZoneInfo(user.timezone)).date()
    row = db.execute(
        select(
            func.count(PendingItem.id),
            func.count(PendingItem.id).filter(PendingItem.planned_date < today),
        )
        .join(Workspace, Workspace.id == PendingItem.workspace_id)
        .join(WorkspaceMember, and_(
            WorkspaceMember.workspace_id == PendingItem.workspace_id,
            WorkspaceMember.user_id == user.id,
        ))
        .where(
            PendingItem.responsible_user_id == user.id,
            PendingItem.is_active.is_(True),
            PendingItem.progress < 100,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def compose_pending_weekly(db: Session, *, user: User, now: datetime) -> NotificationContent | None:
    total, overdue = pending_weekly_counts(db, user=user, now=now)
    if total == 0:
        return None
    parts = [(total, "pendiente activo", "pendientes activos")]
    if overdue:
        parts.append((overdue, "atrasado", "atrasados"))
    return NotificationContent("Pendientes", _compact(parts), "PENDING")


def project_weekly_counts(db: Session, *, user: User, now: datetime) -> tuple[int, int]:
    today = now.astimezone(ZoneInfo(user.timezone)).date()
    stages = (
        select(
            ProjectStage.project_id.label("project_id"),
            ProjectStage.workspace_id.label("workspace_id"),
            func.count(ProjectStage.id).label("stage_count"),
            func.sum(ProjectStage.weight).label("total_weight"),
            func.min(ProjectStage.progress).label("minimum_progress"),
            func.max(ProjectStage.planned_date).label("planned_date"),
        )
        .group_by(ProjectStage.project_id, ProjectStage.workspace_id)
        .subquery()
    )
    incomplete = or_(
        stages.c.stage_count.is_(None),
        stages.c.total_weight != 100,
        stages.c.minimum_progress < 100,
    )
    row = db.execute(
        select(
            func.count(Project.id),
            func.count(Project.id).filter(stages.c.planned_date < today),
        )
        .outerjoin(stages, and_(stages.c.project_id == Project.id, stages.c.workspace_id == Project.workspace_id))
        .join(Workspace, Workspace.id == Project.workspace_id)
        .join(WorkspaceMember, and_(
            WorkspaceMember.workspace_id == Project.workspace_id,
            WorkspaceMember.user_id == user.id,
        ))
        .where(
            Project.leader_user_id == user.id,
            Project.is_active.is_(True),
            incomplete,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def compose_project_weekly(db: Session, *, user: User, now: datetime) -> NotificationContent | None:
    total, overdue = project_weekly_counts(db, user=user, now=now)
    if total == 0:
        return None
    parts = [(total, "proyecto activo", "proyectos activos")]
    if overdue:
        parts.append((overdue, "atrasado", "atrasados"))
    return NotificationContent("Proyectos", _compact(parts), "PROJECTS")


def _current_schedule_matches(db: Session, *, job: NotificationJob, user: User) -> bool:
    preference_type = next((key for key, value in NOTIFICATION_TYPES.items() if value == job.notification_type), None)
    if preference_type is None:
        return False
    preference = db.scalar(select(ReminderPreference).where(
        ReminderPreference.user_id == user.id,
        ReminderPreference.reminder_type == preference_type,
    ))
    from app.services.v2_notifications import DEFAULTS
    local_time = preference.local_time if preference is not None else DEFAULTS[preference_type][1]
    weekdays = preference.weekdays if preference is not None else DEFAULTS[preference_type][2]
    zone = ZoneInfo(user.timezone)
    local_date = job.scheduled_for.astimezone(zone).date()
    if weekdays is not None and local_date.weekday() not in weekdays:
        return False
    return scheduled_instant(local_date, local_time, zone) == job.scheduled_for


def _notification_for_job(db: Session, *, job: NotificationJob, content: NotificationContent) -> Notification:
    notification_type = job.notification_type.value if isinstance(job.notification_type, NotificationType) else job.notification_type
    if job.notification_id is not None:
        notification = db.get(Notification, job.notification_id)
        if notification is not None:
            notification.title = content.title
            notification.body = content.body
            notification.deep_link = _destination_path(content.destination)
            notification.payload = {"type": notification_type, "destination": content.destination}
            return notification
    notification = Notification(
        recipient_user_id=job.user_id,
        notification_type=job.notification_type,
        title=content.title,
        body=content.body,
        deep_link=_destination_path(content.destination),
        payload={"type": notification_type, "destination": content.destination},
        dedup_key=job.dedup_key,
    )
    db.add(notification)
    db.flush()
    job.notification_id = notification.id
    return notification


def _destination_path(destination: str) -> str:
    return {
        "HOME": "/inicio",
        "REVIEW": "/revision",
        "PENDING": "/seguimiento/pendientes",
        "PROJECTS": "/seguimiento/proyectos",
    }[destination]


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
    elif job.notification_type == NotificationType.PENDING_FOLLOW_UP_REMINDER:
        content = compose_pending_weekly(db, user=user, now=now)
    elif job.notification_type == NotificationType.PROJECT_FOLLOW_UP_REMINDER:
        content = compose_project_weekly(db, user=user, now=now)
    else:
        job.status = NotificationJobStatus.CANCELLED
        db.flush()
        return job
    if content is None:
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
