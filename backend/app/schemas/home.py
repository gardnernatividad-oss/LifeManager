from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class HomeTaskAttention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_today: int = Field(ge=0)
    overdue: int = Field(ge=0)


class HomePendingItemAttention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overdue: int = Field(ge=0)


class HomeProjectStepAttention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overdue: int = Field(ge=0)


class HomeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_first_name: str
    local_date: date
    tasks: HomeTaskAttention
    pending_items: HomePendingItemAttention
    project_steps: HomeProjectStepAttention
    last_review_saved_at: datetime | None
    pending_items_last_tracking_saved_at: datetime | None
