import uuid

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import TaskResult


class ReviewTaskRead(BaseModel):
    id: uuid.UUID
    planned_date: date
    name: str
    lock_version: int


class ReviewPendingItemRead(BaseModel):
    id: uuid.UUID
    planned_date: date
    name: str
    progress: int
    comment: str | None
    lock_version: int


class ReviewProjectStepRead(BaseModel):
    id: uuid.UUID
    planned_date: date
    name: str
    weight: Decimal
    progress: int
    comment: str | None
    lock_version: int


class ReviewProjectGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    steps: list[ReviewProjectStepRead]


class ReviewRead(BaseModel):
    review_date: date
    last_review_saved_at: datetime | None
    tasks: list[ReviewTaskRead]
    pending_items: list[ReviewPendingItemRead]
    projects: list[ReviewProjectGroupRead]


class ReviewTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    result: TaskResult
    lock_version: int = Field(ge=1)


class ReviewPendingItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_progress(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("progress", ...) is None:
            raise ValueError("progress cannot be null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "ReviewPendingItemUpdate":
        if not (self.model_fields_set - {"id", "lock_version"}):
            raise ValueError("At least one Pending Item change is required")
        return self


class ReviewProjectStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_progress(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("progress", ...) is None:
            raise ValueError("progress cannot be null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "ReviewProjectStepUpdate":
        if not (self.model_fields_set - {"id", "lock_version"}):
            raise ValueError("At least one Project Step change is required")
        return self


class ReviewSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[ReviewTaskUpdate] = Field(default_factory=list)
    pending_items: list[ReviewPendingItemUpdate] = Field(default_factory=list)
    project_steps: list[ReviewProjectStepUpdate] = Field(default_factory=list)

    @field_validator("tasks", "pending_items", "project_steps")
    @classmethod
    def ids_are_unique(cls, value: list[object]) -> list[object]:
        ids = [item.id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("Review IDs must be unique within each section")
        return value


class ReviewSaveResponse(BaseModel):
    saved_at: datetime
