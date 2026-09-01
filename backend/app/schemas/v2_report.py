import uuid

from datetime import date
from decimal import Decimal

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


class ReportPeriod(_StrictModel):
    date_from: date | None
    date_until: date | None


class ReportCommonFilters(_StrictModel):
    category_id: uuid.UUID | None
    responsible_user_id: uuid.UUID | None


class TaskReportMetrics(_StrictModel):
    total_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    not_completed_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    completion_rate: Decimal | None = Field(default=None, ge=0, le=100)


class TaskReportGroup(TaskReportMetrics):
    key: str
    label: str


class TaskReportEvolution(TaskReportMetrics):
    planned_date: date


class TaskReportRead(_StrictModel):
    period: ReportPeriod
    filters: ReportCommonFilters
    master_task_id: uuid.UUID | None
    custom_tasks: bool | None
    summary: TaskReportMetrics
    by_task: list[TaskReportGroup]
    by_category: list[TaskReportGroup]
    evolution: list[TaskReportEvolution]


class ProgressReportMetrics(_StrictModel):
    total_count: int = Field(ge=0)
    no_iniciado_count: int = Field(ge=0)
    en_proceso_count: int = Field(ge=0)
    finalizado_count: int = Field(ge=0)
    configuracion_incompleta_count: int = Field(default=0, ge=0)
    average_progress: Decimal | None = Field(default=None, ge=0, le=100)


class ComplianceMetrics(_StrictModel):
    en_plazo_count: int = Field(ge=0)
    atrasado_count: int = Field(ge=0)
    con_adelanto_count: int = Field(ge=0)
    a_tiempo_count: int = Field(ge=0)
    con_retraso_count: int = Field(ge=0)


class ProgressCategoryGroup(ProgressReportMetrics):
    category_id: uuid.UUID
    category_name: str


class ProgressEvolution(_StrictModel):
    planned_date: date
    total_count: int = Field(ge=0)
    average_progress: Decimal | None = Field(default=None, ge=0, le=100)


class PendingItemReportRead(_StrictModel):
    period: ReportPeriod
    filters: ReportCommonFilters
    summary: ProgressReportMetrics
    compliance: ComplianceMetrics
    by_category: list[ProgressCategoryGroup]
    evolution: list[ProgressEvolution]


class ProjectReportRow(_StrictModel):
    project_id: uuid.UUID
    project_name: str
    category_id: uuid.UUID
    category_name: str
    planned_date: date | None
    progress: Decimal | None = Field(default=None, ge=0, le=100)
    state: str
    stage_count: int = Field(ge=0)


class ProjectReportRead(_StrictModel):
    period: ReportPeriod
    filters: ReportCommonFilters
    summary: ProgressReportMetrics
    stage_compliance: ComplianceMetrics
    by_category: list[ProgressCategoryGroup]
    by_project: list[ProjectReportRow]
    evolution: list[ProgressEvolution]
