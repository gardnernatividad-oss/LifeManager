import uuid

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pending_item import PendingItemCompliance, PendingItemState


class PendingItemReportPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_from: date | None
    planned_to: date | None


class PendingItemReportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None
    is_active: bool | None
    state: PendingItemState | None
    compliance: PendingItemCompliance | None


class PendingItemReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    inactive_count: int = Field(ge=0)
    no_iniciado_count: int = Field(ge=0)
    en_proceso_count: int = Field(ge=0)
    finalizado_count: int = Field(ge=0)


class PendingItemComplianceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    en_plazo_count: int = Field(ge=0)
    atrasado_count: int = Field(ge=0)
    con_adelanto_count: int = Field(ge=0)
    a_tiempo_count: int = Field(ge=0)
    con_retraso_count: int = Field(ge=0)


class PendingItemDetailSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_atrasado_days: Decimal | None = Field(default=None, ge=0)
    average_con_adelanto_days: Decimal | None = Field(default=None, ge=0)
    average_con_retraso_days: Decimal | None = Field(default=None, ge=0)


class PendingItemCategoryReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    category_name: str
    summary: PendingItemReportSummary
    compliance: PendingItemComplianceSummary


class PendingItemReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: PendingItemReportPeriod
    filters: PendingItemReportFilters
    summary: PendingItemReportSummary
    compliance: PendingItemComplianceSummary
    detail: PendingItemDetailSummary
    by_category: list[PendingItemCategoryReportRow]
