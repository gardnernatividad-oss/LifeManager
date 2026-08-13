import uuid

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TaskReportPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_from: date | None
    planned_to: date | None


class TaskOutcomeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_count: int = Field(ge=0)
    not_completed_count: int = Field(ge=0)
    terminal_count: int = Field(ge=0)
    completion_rate: Decimal | None = Field(default=None, ge=0, le=100)


class TaskMasterTaskReportRow(TaskOutcomeMetrics):
    master_task_id: uuid.UUID
    master_task_name: str
    category_id: uuid.UUID
    category_name: str


class TaskReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: TaskReportPeriod
    summary: TaskOutcomeMetrics
    by_master_task: list[TaskMasterTaskReportRow]
