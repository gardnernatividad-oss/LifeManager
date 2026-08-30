import uuid

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import WorkspaceColor, WorkspaceIcon


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomeTodayCounts(_StrictModel):
    tasks: int
    pending_items: int
    project_stages: int
    activities: int


class HomeWorkspace(_StrictModel):
    id: uuid.UUID
    name: str
    color: WorkspaceColor
    icon: WorkspaceIcon


class HomeUpcomingActivity(_StrictModel):
    id: uuid.UUID
    workspace: HomeWorkspace
    name: str
    starts_at: datetime
    ends_at: datetime


class HomeAttentionItem(_StrictModel):
    type: Literal["TASK", "PENDING_ITEM", "PROJECT_STAGE"]
    id: uuid.UUID
    workspace: HomeWorkspace
    name: str
    planned_date: date
    project_id: uuid.UUID | None = None


class HomeUpcomingDay(_StrictModel):
    date: date
    tasks: int
    pending_items: int
    project_stages: int
    activities: int


class HomeSummaryRead(_StrictModel):
    local_date: date
    today: HomeTodayCounts
    upcoming_activities: list[HomeUpcomingActivity]
    attention: list[HomeAttentionItem]
    upcoming_days: list[HomeUpcomingDay]
