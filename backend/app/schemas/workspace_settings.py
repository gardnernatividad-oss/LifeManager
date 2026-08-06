import uuid

from datetime import datetime, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.models.user_settings import WeekStartsOn
from app.schemas.user_settings import validate_user_timezone


WorkspaceTimezone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WorkspaceSettingsReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: WorkspaceTimezone
    daily_form_enabled: bool
    daily_form_reminder_time: time
    daily_task_generation_enabled: bool
    week_starts_on: WeekStartsOn

    _timezone = field_validator("timezone")(validate_user_timezone)


class WorkspaceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    timezone: str
    daily_form_enabled: bool
    daily_form_reminder_time: time
    daily_task_generation_enabled: bool
    week_starts_on: WeekStartsOn
    created_at: datetime
    updated_at: datetime
