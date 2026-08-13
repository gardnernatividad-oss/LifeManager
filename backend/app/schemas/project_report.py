import uuid

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project import ProjectState


class ProjectReportPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_from: date | None
    planned_to: date | None


class ProjectReportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None
    is_active: bool | None
    state: ProjectState | None


class ProjectReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    inactive_count: int = Field(ge=0)
    no_iniciado_count: int = Field(ge=0)
    en_proceso_count: int = Field(ge=0)
    finalizado_count: int = Field(ge=0)


class ProjectStepComplianceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    en_plazo_count: int = Field(ge=0)
    atrasado_count: int = Field(ge=0)
    con_adelanto_count: int = Field(ge=0)
    a_tiempo_count: int = Field(ge=0)
    con_retraso_count: int = Field(ge=0)


class ProjectStepDetailSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_atrasado_days: Decimal | None = Field(default=None, ge=0)
    average_con_adelanto_days: Decimal | None = Field(default=None, ge=0)
    average_con_retraso_days: Decimal | None = Field(default=None, ge=0)


class ProjectReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    project_name: str
    category_id: uuid.UUID
    category_name: str
    is_active: bool
    planned_date: date | None
    progress: Decimal | None = Field(default=None, ge=0, le=100)
    state: ProjectState | None
    step_count: int = Field(ge=0)


class ProjectReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ProjectReportPeriod
    filters: ProjectReportFilters
    summary: ProjectReportSummary
    step_compliance: ProjectStepComplianceSummary
    detail: ProjectStepDetailSummary
    by_project: list[ProjectReportRow]
