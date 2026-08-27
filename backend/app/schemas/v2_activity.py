import uuid

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ActivityStatus, ParticipantCalendarStatus


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
