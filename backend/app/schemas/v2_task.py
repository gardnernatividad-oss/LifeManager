import uuid

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.recurrence import recurrence_dates
from app.models.enums import GenerationPattern, TaskResult


TaskState = Literal["PROGRAMADA", "PENDIENTE", "COMPLETADA", "NO_REALIZADA"]
TaskMutationScope = Literal["THIS", "THIS_AND_FUTURE"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(_StrictModel):
    master_task_id: uuid.UUID
    planned_date: date
    responsible_user_id: uuid.UUID | None = None


class TaskRecurrence(_StrictModel):
    pattern: GenerationPattern
    date_from: date
    date_until: date
    weekdays: list[int] | None = None
    month_days: list[int] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "TaskRecurrence":
        recurrence_dates(
            pattern=self.pattern,
            date_from=self.date_from,
            date_until=self.date_until,
            weekdays=self.weekdays,
            month_days=self.month_days,
        )
        return self


class RecurringTaskCreate(_StrictModel):
    master_task_id: uuid.UUID
    responsible_user_id: uuid.UUID | None = None
    recurrence: TaskRecurrence


class TaskUpdate(_StrictModel):
    master_task_id: uuid.UUID | None = None
    planned_date: date | None = None
    responsible_user_id: uuid.UUID | None = None
    lock_version: int = Field(ge=1)
    scope: TaskMutationScope = "THIS"

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
    is_generated: bool
    can_edit_this: bool
    can_edit_future: bool
    can_delete_this: bool
    can_delete_future: bool
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


class RecurringTaskCreateResponse(_StrictModel):
    created_count: int = Field(ge=1)
    items: list[TaskRead]
