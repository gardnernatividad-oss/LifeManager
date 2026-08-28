import uuid

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActivityStatus, WorkspaceKind


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalendarWorkspaceRead(_StrictModel):
    id: uuid.UUID
    name: str
    kind: WorkspaceKind


class CalendarPersonRead(_StrictModel):
    user_id: uuid.UUID
    display_name: str
    email: str


class CalendarActivityRead(_StrictModel):
    activity_id: uuid.UUID
    workspace: CalendarWorkspaceRead
    activity_name: str
    category_name: str
    starts_at: datetime
    ends_at: datetime
    organizer: CalendarPersonRead
    participants: list[CalendarPersonRead]
    status: ActivityStatus
    temporal_state: Literal["FUTURE", "IN_PROGRESS", "PAST"]
    lock_version: int
    can_edit: bool
    can_delete: bool
    can_leave_participation: bool


class MyCalendarResponse(_StrictModel):
    items: list[CalendarActivityRead]
