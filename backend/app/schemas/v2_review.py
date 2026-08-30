import uuid

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.v2_pending_item import clean_pending_comment


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
    project_lock_version: int = Field(ge=1)


class GlobalReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_date: date
    tasks: list[ReviewTaskItem]
    pending_items: list[ReviewPendingItem]
    project_stages: list[ReviewProjectStageItem]


class ReviewTaskChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    result: Literal["COMPLETED", "NOT_COMPLETED"]
    lock_version: int = Field(ge=1)


class ReviewPendingItemChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_item_id: uuid.UUID
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = Field(default=None, max_length=2000)
    lock_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_change(self) -> "ReviewPendingItemChange":
        if self.comment is not None:
            self.comment = clean_pending_comment(self.comment)
        if self.progress is None and self.comment is None:
            raise ValueError("Progress or comment is required")
        return self


class ReviewProjectStageChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: uuid.UUID
    progress: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    comment: str | None = Field(default=None, max_length=2000)
    lock_version: int = Field(ge=1)
    project_lock_version: int = Field(ge=1)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        return None if value is None else clean_pending_comment(value)

    @model_validator(mode="after")
    def require_change(self) -> "ReviewProjectStageChange":
        if self.progress is None and self.comment is None:
            raise ValueError("Progress or comment is required")
        return self


class ReviewTaskBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ReviewTaskChange] = Field(min_length=1, max_length=100)


class ReviewPendingItemBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ReviewPendingItemChange] = Field(min_length=1, max_length=100)


class ReviewProjectStageBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ReviewProjectStageChange] = Field(min_length=1, max_length=100)


class ReviewBlockSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saved_ids: list[uuid.UUID]
