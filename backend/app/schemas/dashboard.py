from pydantic import BaseModel, ConfigDict, Field


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_tasks: int = Field(ge=0)
    scheduled_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    not_completed_tasks: int = Field(ge=0)
    cancelled_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)
    tasks_due_today: int = Field(ge=0)
    tasks_due_next_7_days: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)


class DashboardStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completion_rate: float = Field(ge=0, le=100)
    completed_tasks: int = Field(ge=0)
    not_completed_tasks: int = Field(ge=0)
    cancelled_tasks: int = Field(ge=0)
    resolved_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    scheduled_tasks: int = Field(ge=0)
