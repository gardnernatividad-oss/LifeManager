import uuid

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportSummaryCounts(_StrictModel):
    tasks: int = Field(ge=0)
    pending_items: int = Field(ge=0)
    projects: int = Field(ge=0)
    activities: int = Field(ge=0)
    total: int = Field(ge=0)


class ReportSummaryRead(_StrictModel):
    local_date: date
    date_from: date | None
    date_until: date | None
    category_id: uuid.UUID | None
    responsible_user_id: uuid.UUID | None
    counts: ReportSummaryCounts
