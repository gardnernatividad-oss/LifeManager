import uuid

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityStatus, CalendarVisibility, WorkspaceColor, WorkspaceIcon, WorkspaceKind


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalendarWorkspaceRead(_StrictModel):
    id: uuid.UUID
    name: str
    kind: WorkspaceKind
    color: WorkspaceColor = WorkspaceColor.GREEN
    icon: WorkspaceIcon = WorkspaceIcon.HOME


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


class CalendarUntimedRead(_StrictModel):
    id: uuid.UUID
    workspace: CalendarWorkspaceRead
    name: str
    planned_date: date


class CalendarDayCounts(_StrictModel):
    date: date
    activities: int = 0
    tasks: int = 0
    pending_items: int = 0
    project_stages: int = 0


class MyCalendarResponse(_StrictModel):
    items: list[CalendarActivityRead]
    tasks: list[CalendarUntimedRead] = Field(default_factory=list)
    pending_items: list[CalendarUntimedRead] = Field(default_factory=list)
    project_stages: list[CalendarUntimedRead] = Field(default_factory=list)
    daily_counts: list[CalendarDayCounts] = Field(default_factory=list)


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


class CalendarComparisonMember(_StrictModel):
    user_id: uuid.UUID
    display_name: str
    calendar: CalendarComparisonResponse


class CalendarComparisonMultiResponse(_StrictModel):
    members: list[CalendarComparisonMember]


class CalendarVisibilityRead(_StrictModel):
    visibility: CalendarVisibility
    lock_version: int


class CalendarVisibilityUpdate(_StrictModel):
    visibility: CalendarVisibility
    lock_version: int
