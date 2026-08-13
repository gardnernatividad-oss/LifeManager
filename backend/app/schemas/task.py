import enum
import uuid

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import Task, TaskResult


class TaskStatus(str, enum.Enum):
    PROGRAMADA = "PROGRAMADA"
    PENDIENTE = "PENDIENTE"
    COMPLETADA = "COMPLETADA"
    NO_REALIZADA = "NO_REALIZADA"


class BulkTaskPattern(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


def derive_task_status(task: Task, *, local_date: date) -> TaskStatus:
    if task.result == TaskResult.COMPLETED or task.result == TaskResult.COMPLETED.value:
        return TaskStatus.COMPLETADA
    if task.result == TaskResult.NOT_COMPLETED or task.result == TaskResult.NOT_COMPLETED.value:
        return TaskStatus.NO_REALIZADA
    return TaskStatus.PROGRAMADA if task.planned_date > local_date else TaskStatus.PENDIENTE


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_task_id: uuid.UUID
    planned_date: date


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_date: date
    lock_version: int = Field(ge=1)


class TaskDeleteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    lock_version: int = Field(ge=1)


class TaskBulkDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskDeleteItem] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def task_ids_must_be_unique(cls, value: list[TaskDeleteItem]) -> list[TaskDeleteItem]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("task IDs must be unique")
        return value


class TaskBulkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_task_id: uuid.UUID
    start_date: date
    end_date: date
    pattern: BulkTaskPattern
    weekdays: list[int] | None = None

    @model_validator(mode="after")
    def validate_pattern(self) -> "TaskBulkCreate":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if self.pattern is BulkTaskPattern.WEEKLY:
            if not self.weekdays:
                raise ValueError("weekly pattern requires at least one weekday")
            if len(set(self.weekdays)) != len(self.weekdays):
                raise ValueError("weekdays must be unique")
            if any(day < 0 or day > 6 for day in self.weekdays):
                raise ValueError("weekdays must use Monday=0 through Sunday=6")
        elif self.weekdays is not None:
            raise ValueError("weekdays are only valid for weekly pattern")
        return self


class TaskCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TaskMasterTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_id: uuid.UUID
    category: TaskCategoryRead


class TaskRead(BaseModel):
    id: uuid.UUID
    master_task_id: uuid.UUID
    planned_date: date
    status: TaskStatus
    master_task: TaskMasterTaskRead
    lock_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task, *, local_date: date) -> "TaskRead":
        return cls(
            id=task.id,
            master_task_id=task.master_task_id,
            planned_date=task.planned_date,
            status=derive_task_status(task, local_date=local_date),
            master_task=TaskMasterTaskRead.model_validate(task.master_task),
            lock_version=task.lock_version,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskBulkCreateResponse(BaseModel):
    created_count: int
    items: list[TaskRead]


class TaskBulkDeleteResponse(BaseModel):
    deleted_count: int
