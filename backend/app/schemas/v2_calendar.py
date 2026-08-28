import uuid

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityStatus, CalendarVisibility, WorkspaceKind


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


class CalendarComparisonDetail(_StrictModel):
    activity_name: str
    starts_at: datetime
    ends_at: datetime
    temporal_state: Literal["FUTURE", "IN_PROGRESS", "PAST"]


class CalendarBusyBlock(_StrictModel):
    starts_at: datetime
    ends_at: datetime
    occupied: Literal[True] = True


class CalendarComparisonDetails(_StrictModel):
    visibility: Literal[CalendarVisibility.SHOW_DETAILS]
    detailed_events: list[CalendarComparisonDetail]


class CalendarComparisonAvailability(_StrictModel):
    visibility: Literal[CalendarVisibility.AVAILABILITY_ONLY]
    busy_blocks: list[CalendarBusyBlock]


class CalendarComparisonHidden(_StrictModel):
    visibility: Literal[CalendarVisibility.HIDE]


CalendarComparisonResponse = Annotated[
    Union[CalendarComparisonDetails, CalendarComparisonAvailability, CalendarComparisonHidden],
    Field(discriminator="visibility"),
]


class CalendarVisibilityRead(_StrictModel):
    visibility: CalendarVisibility
    lock_version: int


class CalendarVisibilityUpdate(_StrictModel):
    visibility: CalendarVisibility
    lock_version: int
