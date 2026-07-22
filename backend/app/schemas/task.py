import uuid

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.task import Task, TaskOutcome, TaskStatus


TaskTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def derive_task_status(task: Task, *, now: datetime) -> TaskStatus:
    current = _aware_utc(now)
    if task.outcome is not None:
        return TaskStatus(task.outcome.value)
    scheduled_at = _aware_utc(task.scheduled_at)
    return TaskStatus.SCHEDULED if scheduled_at > current else TaskStatus.PENDING


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle
    description: str | None = None
    scheduled_at: datetime
    category_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None

    _validate_scheduled_at = field_validator("scheduled_at")(_aware_utc)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle | None = None
    description: str | None = None
    scheduled_at: datetime | None = None
    category_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("title cannot be null")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_must_not_be_null(cls, value: datetime | None) -> datetime:
        if value is None:
            raise ValueError("scheduled_at cannot be null")
        return _aware_utc(value)


class TaskRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_id: uuid.UUID
    category_id: uuid.UUID | None
    project_id: uuid.UUID | None
    task_series_id: uuid.UUID | None
    title: str
    description: str | None
    scheduled_at: datetime
    status: TaskStatus
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task, *, now: datetime | None = None) -> "TaskRead":
        boundary = now or datetime.now(timezone.utc)
        return cls(
            id=task.id,
            workspace_id=task.workspace_id,
            created_by_id=task.created_by_id,
            category_id=task.category_id,
            project_id=task.project_id,
            task_series_id=task.task_series_id,
            title=task.title,
            description=task.description,
            scheduled_at=task.scheduled_at,
            status=derive_task_status(task, now=boundary),
            resolved_at=task.resolved_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
