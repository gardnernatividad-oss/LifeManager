import uuid

from datetime import datetime, time
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.user_settings import WeekStartsOn


Locale = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


def validate_user_timezone(value: str) -> str:
    if not value.strip():
        raise ValueError("timezone must not be blank")
    try:
        return ZoneInfo(value.strip()).key
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("timezone must be a valid IANA identifier") from error


class UserSettingsReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str
    locale: Locale
    week_starts_on: WeekStartsOn
    daily_form_reminders_enabled: bool
    task_due_reminders_enabled: bool
    task_overdue_reminders_enabled: bool
    daily_form_reminder_time: time
    task_due_reminder_minutes: int = Field(ge=0, le=1440)

    _timezone = field_validator("timezone")(validate_user_timezone)


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    user_id: uuid.UUID
    timezone: str
    locale: str
    week_starts_on: WeekStartsOn
    daily_form_reminders_enabled: bool
    task_due_reminders_enabled: bool
    task_overdue_reminders_enabled: bool
    daily_form_reminder_time: time
    task_due_reminder_minutes: int
    created_at: datetime
    updated_at: datetime
