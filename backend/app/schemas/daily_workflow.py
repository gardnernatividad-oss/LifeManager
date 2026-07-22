import enum
import uuid

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.daily_task_generation import DailyTaskGenerationResponse


class DailyWorkflowStatus(str, enum.Enum):
    ACTION_REQUIRED = "ACTION_REQUIRED"
    READY = "READY"


class DailyWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: uuid.UUID
    user_id: uuid.UUID
    workflow_date: date
    workflow_status: DailyWorkflowStatus
    form_required: bool
    form_submitted: bool
    definition_id: uuid.UUID | None
    submission_id: uuid.UUID | None
    task_generation: DailyTaskGenerationResponse
    evaluated_at: datetime
