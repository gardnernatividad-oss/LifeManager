import uuid

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    planned_date: date
    lock_version: int = Field(ge=1)


class ReviewTaskItem(_ReviewItem):
    task_name: str


class ReviewPendingItem(_ReviewItem):
    pending_item_name: str
    progress: int = Field(ge=0, le=100)


class ReviewProjectStageItem(_ReviewItem):
    project_id: uuid.UUID
    project_name: str
    stage_name: str
    progress: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class GlobalReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_date: date
    tasks: list[ReviewTaskItem]
    pending_items: list[ReviewPendingItem]
    project_stages: list[ReviewProjectStageItem]
