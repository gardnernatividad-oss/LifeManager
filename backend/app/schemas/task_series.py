import uuid

from datetime import datetime, timezone
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models.task_series import TaskSeriesFrequency


TaskSeriesTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


def validate_timezone(value: str) -> str:
    if not value or value.startswith(('+', '-')):
        raise ValueError("timezone must be a valid IANA identifier")
    try:
        return ZoneInfo(value).key
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("timezone must be a valid IANA identifier") from error


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def validate_recurrence_state(
    *,
    frequency: TaskSeriesFrequency,
    weekdays: list[int] | None,
    month_day: int | None,
    starts_at: datetime,
    ends_at: datetime | None,
) -> None:
    if frequency is TaskSeriesFrequency.DAILY and (weekdays is not None or month_day is not None):
        raise ValueError("daily recurrence cannot define weekdays or month_day")
    if frequency is TaskSeriesFrequency.WEEKLY and (not weekdays or month_day is not None):
        raise ValueError("weekly recurrence requires weekdays and cannot define month_day")
    if frequency is TaskSeriesFrequency.MONTHLY and (weekdays is not None or month_day is None):
        raise ValueError("monthly recurrence requires month_day and cannot define weekdays")
    if ends_at is not None and ends_at <= starts_at:
        raise ValueError("ends_at must be later than starts_at")


class TaskSeriesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskSeriesTitle
    description: str | None = None
    timezone: str
    frequency: TaskSeriesFrequency
    interval: int = Field(default=1, ge=1, le=365)
    weekdays: list[int] | None = None
    month_day: int | None = Field(default=None, ge=1, le=31)
    starts_at: datetime
    ends_at: datetime | None = None
    category_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None

    _timezone = field_validator("timezone")(validate_timezone)
    _starts_at = field_validator("starts_at")(aware_utc)
    _ends_at = field_validator("ends_at")(lambda value: None if value is None else aware_utc(value))

    @field_validator("weekdays")
    @classmethod
    def canonicalize_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("weekdays must contain values from 0 through 6")
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_shape(self) -> "TaskSeriesCreate":
        validate_recurrence_state(
            frequency=self.frequency,
            weekdays=self.weekdays,
            month_day=self.month_day,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        )
        return self


class TaskSeriesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskSeriesTitle | None = None
    description: str | None = None
    timezone: str | None = None
    frequency: TaskSeriesFrequency | None = None
    interval: int | None = Field(default=None, ge=1, le=365)
    weekdays: list[int] | None = None
    month_day: int | None = Field(default=None, ge=1, le=31)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    category_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None

    @field_validator("title", "timezone", "frequency", "interval", "starts_at")
    @classmethod
    def required_fields_must_not_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    _timezone = field_validator("timezone")(validate_timezone)
    _starts_at = field_validator("starts_at")(aware_utc)
    _ends_at = field_validator("ends_at")(lambda value: None if value is None else aware_utc(value))

    @field_validator("weekdays")
    @classmethod
    def canonicalize_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("weekdays must contain values from 0 through 6")
        return sorted(set(value))


class TaskSeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_id: uuid.UUID
    category_id: uuid.UUID | None
    project_id: uuid.UUID | None
    title: str
    description: str | None
    timezone: str
    frequency: TaskSeriesFrequency
    interval: int
    weekdays: list[int] | None
    month_day: int | None
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TaskSeriesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskSeriesRead]
    total: int = Field(ge=0)


class TaskSeriesMaterializeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime

    _window_start = field_validator("window_start")(aware_utc)
    _window_end = field_validator("window_end")(aware_utc)

    @model_validator(mode="after")
    def validate_window(self) -> "TaskSeriesMaterializeRequest":
        if self.window_end < self.window_start:
            raise ValueError("window_end must be equal to or later than window_start")
        return self


class TaskSeriesMaterializeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_count: int = Field(ge=0)
    generated_task_ids: list[uuid.UUID]


class TaskSeriesSynchronizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    deleted_count: int = Field(ge=0)
    created_task_ids: list[uuid.UUID]
    updated_task_ids: list[uuid.UUID]
    deleted_task_ids: list[uuid.UUID]
