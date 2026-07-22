import uuid

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyTaskGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: uuid.UUID
    generation_date: date
    eligible_series_count: int = Field(ge=0)
    created_task_count: int = Field(ge=0)
    skipped_existing_count: int = Field(ge=0)
    created_task_ids: list[uuid.UUID]
    generated_at: datetime
