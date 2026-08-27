import uuid

from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.recurrence import recurrence_dates
from app.models.enums import ActivityStatus, GenerationPattern, ParticipantCalendarStatus


ActivityTemporalState = Literal["FUTURE", "IN_PROGRESS", "PAST"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value


class ActivityCreate(_StrictModel):
    activity_master_id: uuid.UUID
    organizer_user_id: uuid.UUID | None = None
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list)
    starts_at: datetime
    ends_at: datetime

    _starts = field_validator("starts_at")(_aware)
    _ends = field_validator("ends_at")(_aware)

    @model_validator(mode="after")
    def validate_activity(self) -> "ActivityCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if len(set(self.participant_user_ids)) != len(self.participant_user_ids):
            raise ValueError("participant_user_ids must be unique")
        return self


class ActivityRecurrence(_StrictModel):
    pattern: GenerationPattern
    date_from: date
    date_until: date
    weekdays: list[int] | None = None
    month_days: list[int] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ActivityRecurrence":
        recurrence_dates(pattern=self.pattern, date_from=self.date_from, date_until=self.date_until,
                         weekdays=self.weekdays, month_days=self.month_days)
        return self


class RecurringActivityCreate(_StrictModel):
    activity_master_id: uuid.UUID
    organizer_user_id: uuid.UUID | None = None
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list)
    start_time: time
    end_time: time
    timezone: str = Field(min_length=1, max_length=100)
    recurrence: ActivityRecurrence

    @model_validator(mode="after")
    def validate_activity(self) -> "RecurringActivityCreate":
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError("local times must not include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if len(set(self.participant_user_ids)) != len(self.participant_user_ids):
            raise ValueError("participant_user_ids must be unique")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return self


class ActivityUpdate(_StrictModel):
    activity_master_id: uuid.UUID | None = None
    organizer_user_id: uuid.UUID | None = None
    participant_user_ids: list[uuid.UUID] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, value: object) -> object:
        if isinstance(value, dict):
            editable = ("activity_master_id", "organizer_user_id", "participant_user_ids", "starts_at", "ends_at")
            for field in editable:
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
            if not any(field in value for field in editable):
                raise ValueError("at least one editable field is required")
        return value

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_datetime(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else value

    @field_validator("participant_user_ids")
    @classmethod
    def validate_participants(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("participant_user_ids must be unique")
        return value


class ActivityVersion(_StrictModel):
    lock_version: int = Field(ge=1)


class ActivityParticipantRead(_StrictModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    calendar_status: ParticipantCalendarStatus


class ActivityRead(_StrictModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    activity_master_id: uuid.UUID | None
    activity_master_name: str | None
    category_id: uuid.UUID
    category_name: str
    title: str
    organizer_user_id: uuid.UUID
    organizer_display_name: str
    organizer_email: str
    participants: list[ActivityParticipantRead]
    starts_at: datetime
    ends_at: datetime
    status: ActivityStatus
    temporal_state: ActivityTemporalState
    lock_version: int
    is_generated: bool
    can_edit: bool
    can_delete: bool
    can_leave_participation: bool
    created_at: datetime
    updated_at: datetime


class ActivityListResponse(_StrictModel):
    items: list[ActivityRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class RecurringActivityCreateResponse(_StrictModel):
    created_count: int = Field(ge=1)
    items: list[ActivityRead]
