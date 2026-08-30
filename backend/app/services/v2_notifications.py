import base64
import hashlib
import hmac
import uuid

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models import (
    Activity,
    ActivityParticipant,
    ActivityReminder,
    NotificationJob,
    PushSubscription,
    ReminderPreference,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.enums import (
    AccountStatus,
    ActivityStatus,
    MembershipStatus,
    NotificationType,
    ParticipantCalendarStatus,
    ReminderType,
    ScheduleKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_notifications import NotificationPreferencesUpdate, PushSubscriptionCreate


class NotificationPreferenceConflictError(Exception): pass
class PushSubscriptionConflictError(Exception): pass
class PushSubscriptionNotFoundError(Exception): pass


DEFAULTS = {
    ReminderType.DAILY_SUMMARY: (ScheduleKind.DAILY, time(7), None),
    ReminderType.DAILY_REVIEW: (ScheduleKind.DAILY, time(21), None),
    ReminderType.PENDING_FOLLOW_UP: (ScheduleKind.WEEKLY, time(22), [6]),
    ReminderType.PROJECT_FOLLOW_UP: (ScheduleKind.WEEKLY, time(22, 30), [6]),
    ReminderType.ACTIVITY_REMINDERS: (None, None, None),
}
SCHEDULED_TYPES = tuple(item for item in DEFAULTS if item != ReminderType.ACTIVITY_REMINDERS)
NOTIFICATION_TYPES = {
    ReminderType.DAILY_SUMMARY: NotificationType.DAILY_SUMMARY_REMINDER,
    ReminderType.DAILY_REVIEW: NotificationType.DAILY_REVIEW_REMINDER,
    ReminderType.PENDING_FOLLOW_UP: NotificationType.PENDING_FOLLOW_UP_REMINDER,
    ReminderType.PROJECT_FOLLOW_UP: NotificationType.PROJECT_FOLLOW_UP_REMINDER,
}


def get_preferences(db: Session, *, user_id: uuid.UUID, persist_missing: bool = False) -> list[ReminderPreference]:
    existing = {row.reminder_type: row for row in db.scalars(select(ReminderPreference).where(ReminderPreference.user_id == user_id)).all()}
    for reminder_type, (kind, local_time, weekdays) in DEFAULTS.items():
        if reminder_type not in existing:
            row = ReminderPreference(user_id=user_id, reminder_type=reminder_type, is_enabled=True, schedule_kind=kind, local_time=local_time, weekdays=weekdays, lock_version=1)
            if persist_missing: db.add(row)
            existing[reminder_type] = row
    if persist_missing: db.flush()
    return [existing[item] for item in DEFAULTS]


def update_preferences(db: Session, *, user_id: uuid.UUID, preferences_in: NotificationPreferencesUpdate) -> list[ReminderPreference]:
    rows = get_preferences(db, user_id=user_id, persist_missing=True)
    by_type = {row.reminder_type: row for row in rows}
    updates = {
        ReminderType.DAILY_SUMMARY: preferences_in.daily_summary,
        ReminderType.DAILY_REVIEW: preferences_in.daily_review,
        ReminderType.PENDING_FOLLOW_UP: preferences_in.pending_weekly,
        ReminderType.PROJECT_FOLLOW_UP: preferences_in.project_weekly,
        ReminderType.ACTIVITY_REMINDERS: preferences_in.activity_reminders,
    }
    if any(by_type[reminder_type].lock_version != incoming.lock_version for reminder_type, incoming in updates.items()):
        raise NotificationPreferenceConflictError
    for reminder_type, incoming in updates.items():
        row = by_type[reminder_type]
        row.is_enabled = incoming.enabled
        if reminder_type != ReminderType.ACTIVITY_REMINDERS:
            row.local_time = incoming.local_time
            row.weekdays = [incoming.weekday] if row.schedule_kind == ScheduleKind.WEEKLY else None
        row.lock_version += 1
    db.flush()
    return rows


def _valid_instants(day: date, local_time: time, zone: ZoneInfo) -> list[datetime]:
    naive = datetime.combine(day, local_time)
    instants: set[datetime] = set()
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            instants.add(candidate)
    return sorted(instants)


def scheduled_instant(day: date, local_time: time, zone: ZoneInfo) -> datetime:
    instants = _valid_instants(day, local_time, zone)
    if instants:
        return instants[0]
    candidate = datetime.combine(day, local_time)
    for minutes in range(1, 181):
        later = candidate + timedelta(minutes=minutes)
        instants = _valid_instants(later.date(), later.time(), zone)
        if instants:
            return instants[0]
    raise ValueError("No valid local notification time")


def generate_scheduled_jobs(db: Session, *, window_start: datetime, window_end: datetime) -> int:
    if window_start.tzinfo is None or window_end.tzinfo is None or window_start >= window_end:
        raise ValueError("Notification window must be aware and non-empty")
    users = db.scalars(select(User).where(User.account_status == AccountStatus.ACTIVE)).all()
    persisted = db.scalars(select(ReminderPreference).where(ReminderPreference.reminder_type.in_(SCHEDULED_TYPES))).all()
    persisted_by_user = {(row.user_id, row.reminder_type): row for row in persisted}
    rows = []
    for user in users:
        for reminder_type in SCHEDULED_TYPES:
            preference = persisted_by_user.get((user.id, reminder_type))
            if preference is None:
                kind, local_time, weekdays = DEFAULTS[reminder_type]
                preference = ReminderPreference(user_id=user.id, reminder_type=reminder_type, is_enabled=True, schedule_kind=kind, local_time=local_time, weekdays=weekdays, lock_version=1)
            if preference.is_enabled:
                rows.append((preference, user))
    values = []
    for preference, user in rows:
        zone = ZoneInfo(user.timezone)
        first = window_start.astimezone(zone).date() - timedelta(days=1)
        last = window_end.astimezone(zone).date() + timedelta(days=1)
        day = first
        while day <= last:
            if preference.schedule_kind == ScheduleKind.DAILY or day.weekday() in (preference.weekdays or []):
                due = scheduled_instant(day, preference.local_time, zone)
                if window_start <= due < window_end:
                    notification_type = NOTIFICATION_TYPES[preference.reminder_type]
                    values.append({"id": uuid.uuid4(), "user_id": user.id, "notification_type": notification_type, "scheduled_for": due, "dedup_key": f"{user.id}:{notification_type}:{day.isoformat()}"})
            day += timedelta(days=1)
    if not values:
        return 0
    result = db.execute(insert(NotificationJob).values(values).on_conflict_do_nothing(index_elements=[NotificationJob.dedup_key]).returning(NotificationJob.id))
    db.flush()
    return len(result.scalars().all())


def job_is_still_eligible(db: Session, *, job: NotificationJob) -> bool:
    preference_type = next((key for key, value in NOTIFICATION_TYPES.items() if value == job.notification_type), None)
    if preference_type is None:
        return False
    user_active = db.scalar(select(User.id).where(User.id == job.user_id, User.account_status == AccountStatus.ACTIVE)) is not None
    if not user_active:
        return False
    preference = db.scalar(select(ReminderPreference).where(ReminderPreference.user_id == job.user_id, ReminderPreference.reminder_type == preference_type))
    return preference is None or preference.is_enabled


def activity_reminder_is_still_eligible(
    db: Session,
    *,
    reminder_id: uuid.UUID,
    user_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Revalidate an Activity reminder immediately before delivery."""
    eligible_id = db.scalar(
        select(ActivityReminder.id)
        .join(
            ActivityParticipant,
            (ActivityParticipant.activity_id == ActivityReminder.activity_id)
            & (ActivityParticipant.workspace_id == ActivityReminder.workspace_id)
            & (ActivityParticipant.user_id == ActivityReminder.user_id),
        )
        .join(
            Activity,
            (Activity.id == ActivityReminder.activity_id)
            & (Activity.workspace_id == ActivityReminder.workspace_id),
        )
        .join(Workspace, Workspace.id == ActivityReminder.workspace_id)
        .join(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == ActivityReminder.workspace_id)
            & (WorkspaceMember.user_id == ActivityReminder.user_id),
        )
        .where(
            ActivityReminder.id == reminder_id,
            ActivityReminder.user_id == user_id,
            ActivityReminder.is_enabled.is_(True),
            ActivityParticipant.calendar_status == ParticipantCalendarStatus.VISIBLE,
            Activity.status == ActivityStatus.SCHEDULED,
            Activity.starts_at > now,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
    )
    if eligible_id is None:
        return False
    preference = db.scalar(
        select(ReminderPreference).where(
            ReminderPreference.user_id == user_id,
            ReminderPreference.reminder_type == ReminderType.ACTIVITY_REMINDERS,
        )
    )
    return preference is None or preference.is_enabled


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def register_push_subscription(db: Session, *, user_id: uuid.UUID, subscription_in: PushSubscriptionCreate, user_agent: str | None) -> PushSubscription:
    endpoint = str(subscription_in.endpoint).encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), endpoint, hashlib.sha256).digest()
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == digest).with_for_update())
    if existing is not None and existing.user_id != user_id:
        raise PushSubscriptionConflictError
    cipher = _fernet()
    row = existing or PushSubscription(user_id=user_id, endpoint_hash=digest)
    row.endpoint_ciphertext = cipher.encrypt(endpoint)
    row.p256dh_ciphertext = cipher.encrypt(subscription_in.keys.p256dh.encode())
    row.auth_ciphertext = cipher.encrypt(subscription_in.keys.auth.encode())
    row.user_agent = user_agent[:500] if user_agent else None
    row.is_active = True; row.invalidated_at = None
    if existing is None: db.add(row)
    try:
        db.flush()
    except IntegrityError as error:
        if "uq_push_subscriptions_endpoint_hash" in str(error.orig):
            raise PushSubscriptionConflictError from error
        raise
    return row


def unregister_push_subscription(db: Session, *, user_id: uuid.UUID, subscription_id: uuid.UUID, now: datetime) -> None:
    row = db.scalar(select(PushSubscription).where(PushSubscription.id == subscription_id, PushSubscription.user_id == user_id).with_for_update())
    if row is None: raise PushSubscriptionNotFoundError
    if row.is_active:
        row.is_active = False; row.invalidated_at = now; db.flush()
