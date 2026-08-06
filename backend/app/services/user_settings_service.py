from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings import UserSettings, WeekStartsOn
from app.schemas.user_settings import UserSettingsReplace


class UserSettingsValidationError(ValueError):
    pass


def _validate_timezone(value: str) -> str:
    try:
        return ZoneInfo(value.strip()).key
    except (AttributeError, ZoneInfoNotFoundError, ValueError) as error:
        raise UserSettingsValidationError("timezone must be a valid IANA identifier") from error


def _normalize_locale(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise UserSettingsValidationError("locale must not be blank")
    if len(normalized) > 20:
        raise UserSettingsValidationError("locale must not exceed 20 characters")
    return normalized


def _new_default_settings(user_id) -> UserSettings:
    return UserSettings(
        user_id=user_id, timezone="America/Lima", locale="es-PE",
        week_starts_on=WeekStartsOn.MONDAY,
        daily_form_reminders_enabled=True, task_due_reminders_enabled=True,
        task_overdue_reminders_enabled=True, daily_form_reminder_time=time(9),
        task_due_reminder_minutes=60,
    )


def _get_user_settings(db: Session, *, user_id) -> UserSettings | None:
    return db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))


def get_or_create_user_settings(db: Session, *, current_user: User) -> UserSettings:
    settings = _get_user_settings(db, user_id=current_user.id)
    if settings is None:
        settings = _new_default_settings(current_user.id)
        db.add(settings); db.flush()
    return settings


def replace_user_settings(db: Session, *, current_user: User, settings_in: UserSettingsReplace) -> UserSettings:
    settings = _get_user_settings(db, user_id=current_user.id)
    if settings is None:
        settings = _new_default_settings(current_user.id); db.add(settings)
    values = settings_in.model_dump()
    values["timezone"] = _validate_timezone(values["timezone"])
    values["locale"] = _normalize_locale(values["locale"])
    for field, value in values.items(): setattr(settings, field, value)
    db.flush(); return settings
