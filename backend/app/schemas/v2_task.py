import uuid

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TaskResult


TaskState = Literal["PROGRAMADA", "PENDIENTE", "COMPLETADA", "NO_REALIZADA"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(_StrictModel):
    master_task_id: uuid.UUID
    planned_date: date
    responsible_user_id: uuid.UUID | None = None


class TaskUpdate(_StrictModel):
    master_task_id: uuid.UUID | None = None
    planned_date: date | None = None
    responsible_user_id: uuid.UUID | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_or_empty_update(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("master_task_id", "planned_date", "responsible_user_id"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
            if not any(field in value for field in ("master_task_id", "planned_date", "responsible_user_id")):
                raise ValueError("at least one editable field is required")
        return value


class TaskVersionRequest(_StrictModel):
    lock_version: int = Field(ge=1)


class TaskRead(_StrictModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    master_task_id: uuid.UUID
    master_task_name: str
    category_id: uuid.UUID
    category_name: str
    responsible_user_id: uuid.UUID
    responsible_display_name: str
    responsible_email: str
    planned_date: date
    state: TaskState
    result: TaskResult | None
    resolved_at: datetime | None
    resolved_by_user_id: uuid.UUID | None
    lock_version: int
    can_edit: bool
    can_resolve: bool
    can_delete: bool
    created_at: datetime
    updated_at: datetime


class TaskListResponse(_StrictModel):
    items: list[TaskRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
