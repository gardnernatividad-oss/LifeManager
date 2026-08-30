import uuid

from datetime import time

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ScheduledPreference(_Strict):
    enabled: bool
    local_time: time
    weekday: int | None = Field(default=None, ge=0, le=6)
    lock_version: int = Field(ge=1)


class ActivityReminderPreference(_Strict):
    enabled: bool
    lock_version: int = Field(ge=1)


class NotificationPreferencesRead(_Strict):
    daily_summary: ScheduledPreference
    daily_review: ScheduledPreference
    pending_weekly: ScheduledPreference
    project_weekly: ScheduledPreference
    activity_reminders: ActivityReminderPreference


class ScheduledPreferenceUpdate(_Strict):
    enabled: bool
    local_time: time
    weekday: int | None = Field(default=None, ge=0, le=6)
    lock_version: int = Field(ge=1)


class ActivityReminderPreferenceUpdate(_Strict):
    enabled: bool
    lock_version: int = Field(ge=1)


class NotificationPreferencesUpdate(_Strict):
    daily_summary: ScheduledPreferenceUpdate
    daily_review: ScheduledPreferenceUpdate
    pending_weekly: ScheduledPreferenceUpdate
    project_weekly: ScheduledPreferenceUpdate
    activity_reminders: ActivityReminderPreferenceUpdate

    @model_validator(mode="after")
    def validate_weekdays(self) -> "NotificationPreferencesUpdate":
        if self.daily_summary.weekday is not None or self.daily_review.weekday is not None:
            raise ValueError("Daily preferences do not accept weekday")
        if self.pending_weekly.weekday is None or self.project_weekly.weekday is None:
            raise ValueError("Weekly preferences require weekday")
        return self


class PushKeys(_Strict):
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)


class PushSubscriptionCreate(_Strict):
    endpoint: HttpUrl
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Push endpoint must use HTTPS")
        return value


class PushSubscriptionRead(_Strict):
    id: uuid.UUID
    is_active: bool
