import uuid

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.task import TaskPriority, TaskStatus


TaskTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    position: int = Field(default=0, ge=0)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    position: int | None = Field(default=None, ge=0)
    is_archived: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("title cannot be null")
        return value


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    completed_at: datetime | None
    position: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskRead]
    total: int = Field(ge=0)
