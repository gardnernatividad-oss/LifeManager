import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Request, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.models.enums import ReminderType
from app.schemas.v2_notifications import ActivityReminderPreference, NotificationPreferencesRead, NotificationPreferencesUpdate, PushSubscriptionCreate, PushSubscriptionRead, ScheduledPreference
from app.services.v2_notifications import NotificationPreferenceConflictError, PushSubscriptionConflictError, PushSubscriptionNotFoundError, get_preferences, register_push_subscription, unregister_push_subscription, update_preferences


router = APIRouter(tags=["V2 Notifications"])


def _preferences(rows) -> NotificationPreferencesRead:
    values = {row.reminder_type: row for row in rows}
    def scheduled(reminder_type: ReminderType) -> ScheduledPreference:
        row = values[reminder_type]
        return ScheduledPreference(enabled=row.is_enabled, local_time=row.local_time, weekday=row.weekdays[0] if row.weekdays else None, lock_version=row.lock_version)
    activity = values[ReminderType.ACTIVITY_REMINDERS]
    return NotificationPreferencesRead(
        daily_summary=scheduled(ReminderType.DAILY_SUMMARY), daily_review=scheduled(ReminderType.DAILY_REVIEW),
        pending_weekly=scheduled(ReminderType.PENDING_FOLLOW_UP), project_weekly=scheduled(ReminderType.PROJECT_FOLLOW_UP),
        activity_reminders=ActivityReminderPreference(enabled=activity.is_enabled, lock_version=activity.lock_version),
    )


@router.get("/notification-preferences", response_model=NotificationPreferencesRead)
def read_notification_preferences(db: SessionDependency, account: UsableAccount) -> NotificationPreferencesRead:
    return _preferences(get_preferences(db, user_id=account.id))


@router.put("/notification-preferences", response_model=NotificationPreferencesRead)
def replace_notification_preferences(preferences_in: NotificationPreferencesUpdate, db: SessionDependency, account: UsableAccount) -> NotificationPreferencesRead:
    try:
        rows = update_preferences(db, user_id=account.id, preferences_in=preferences_in)
        db.commit()
    except NotificationPreferenceConflictError as error:
        db.rollback(); raise V2APIError(status_code=status.HTTP_409_CONFLICT, code="NOTIFICATION_PREFERENCES_CONFLICT", message="Las preferencias cambiaron. Vuelve a cargarlas.") from error
    except Exception:
        db.rollback(); raise
    return _preferences(rows)


@router.post("/push-subscriptions", response_model=PushSubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_push_subscription(subscription_in: PushSubscriptionCreate, request: Request, db: SessionDependency, account: UsableAccount) -> PushSubscriptionRead:
    try:
        row = register_push_subscription(db, user_id=account.id, subscription_in=subscription_in, user_agent=request.headers.get("user-agent"))
        db.commit(); db.refresh(row)
    except PushSubscriptionConflictError as error:
        db.rollback(); raise V2APIError(status_code=status.HTTP_409_CONFLICT, code="PUSH_SUBSCRIPTION_CONFLICT", message="La suscripción ya pertenece a otra cuenta.") from error
    except Exception:
        db.rollback(); raise
    return PushSubscriptionRead.model_validate(row)


@router.delete("/push-subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(subscription_id: uuid.UUID, db: SessionDependency, account: UsableAccount) -> None:
    try:
        unregister_push_subscription(db, user_id=account.id, subscription_id=subscription_id, now=datetime.now(timezone.utc)); db.commit()
    except PushSubscriptionNotFoundError as error:
        db.rollback(); raise V2APIError(status_code=status.HTTP_404_NOT_FOUND, code="PUSH_SUBSCRIPTION_NOT_FOUND", message="No se encontró la suscripción.") from error
    except Exception:
        db.rollback(); raise
