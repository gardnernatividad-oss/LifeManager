import enum
import uuid

from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ReminderType(str, enum.Enum):
    DAILY_FORM_REQUIRED = "DAILY_FORM_REQUIRED"
    TASK_DUE = "TASK_DUE"
    TASK_OVERDUE = "TASK_OVERDUE"


class ReminderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_type: ReminderType
    entity_id: uuid.UUID
    title: str
    scheduled_for: AwareDatetime
    local_date: date
    metadata: dict[str, str | int | float | bool | None]


class ReminderEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: uuid.UUID
    user_id: uuid.UUID
    evaluated_at: AwareDatetime
    local_date: date
    timezone: str
    reminder_count: int = Field(ge=0)
    reminders: list[ReminderItem]
