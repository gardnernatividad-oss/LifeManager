import uuid

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Category, PendingItem
from app.schemas.pending_item import PendingItemCompliance, PendingItemState
from app.schemas.pending_item_report import (
    PendingItemCategoryReportRow,
    PendingItemComplianceSummary,
    PendingItemDetailSummary,
    PendingItemReportFilters,
    PendingItemReportPeriod,
    PendingItemReportResponse,
    PendingItemReportSummary,
)


class PendingItemReportCategoryNotFoundError(LookupError):
    pass


def _compliance_predicates(local_date: date):
    has_planned_date = PendingItem.planned_date.is_not(None)
    return {
        PendingItemCompliance.EN_PLAZO: (
            has_planned_date
            & PendingItem.completion_date.is_(None)
            & (PendingItem.planned_date >= local_date)
        ),
        PendingItemCompliance.ATRASADO: (
            has_planned_date
            & PendingItem.completion_date.is_(None)
            & (PendingItem.planned_date < local_date)
        ),
        PendingItemCompliance.CON_ADELANTO: (
            has_planned_date
            & (PendingItem.completion_date < PendingItem.planned_date)
        ),
        PendingItemCompliance.A_TIEMPO: (
            has_planned_date
            & (PendingItem.completion_date == PendingItem.planned_date)
        ),
        PendingItemCompliance.CON_RETRASO: (
            has_planned_date
            & (PendingItem.completion_date > PendingItem.planned_date)
        ),
    }


def _population_filters(
    *,
    workspace_id: uuid.UUID,
    local_date: date,
    planned_from: date | None,
    planned_to: date | None,
    category_id: uuid.UUID | None,
    is_active: bool | None,
    state: PendingItemState | None,
    compliance: PendingItemCompliance | None,
):
    filters = [PendingItem.workspace_id == workspace_id]
    if planned_from is not None:
        filters.append(PendingItem.planned_date >= planned_from)
    if planned_to is not None:
        filters.append(PendingItem.planned_date <= planned_to)
    if category_id is not None:
        filters.append(PendingItem.category_id == category_id)
    if is_active is not None:
        filters.append(PendingItem.is_active == is_active)
    if state is PendingItemState.NO_INICIADO:
        filters.append(PendingItem.progress == 0)
    elif state is PendingItemState.EN_PROCESO:
        filters.append(PendingItem.progress.between(1, 99))
    elif state is PendingItemState.FINALIZADO:
        filters.append(PendingItem.progress == 100)
    if compliance is not None:
        filters.append(_compliance_predicates(local_date)[compliance])
    return filters


def _aggregate_columns(local_date: date, *, include_detail: bool):
    compliance = _compliance_predicates(local_date)
    columns = [
        func.count().label("total_count"),
        func.count().filter(PendingItem.is_active.is_(True)).label("active_count"),
        func.count().filter(PendingItem.is_active.is_(False)).label("inactive_count"),
        func.count().filter(PendingItem.progress == 0).label("no_iniciado_count"),
        func.count().filter(PendingItem.progress.between(1, 99)).label("en_proceso_count"),
        func.count().filter(PendingItem.progress == 100).label("finalizado_count"),
        func.count().filter(compliance[PendingItemCompliance.EN_PLAZO]).label("en_plazo_count"),
        func.count().filter(compliance[PendingItemCompliance.ATRASADO]).label("atrasado_count"),
        func.count().filter(compliance[PendingItemCompliance.CON_ADELANTO]).label("con_adelanto_count"),
        func.count().filter(compliance[PendingItemCompliance.A_TIEMPO]).label("a_tiempo_count"),
        func.count().filter(compliance[PendingItemCompliance.CON_RETRASO]).label("con_retraso_count"),
    ]
    if include_detail:
        columns.extend(
            [
                func.avg(
                    case(
                        (compliance[PendingItemCompliance.ATRASADO], local_date - PendingItem.planned_date),
                        else_=None,
                    )
                ).label("average_atrasado_days"),
                func.avg(
                    case(
                        (
                            compliance[PendingItemCompliance.CON_ADELANTO],
                            PendingItem.planned_date - PendingItem.completion_date,
                        ),
                        else_=None,
                    )
                ).label("average_con_adelanto_days"),
                func.avg(
                    case(
                        (
                            compliance[PendingItemCompliance.CON_RETRASO],
                            PendingItem.completion_date - PendingItem.planned_date,
                        ),
                        else_=None,
                    )
                ).label("average_con_retraso_days"),
            ]
        )
    return columns


def _summary(values) -> PendingItemReportSummary:
    return PendingItemReportSummary(
        **{name: int(values[name]) for name in (
            "total_count", "active_count", "inactive_count", "no_iniciado_count",
            "en_proceso_count", "finalizado_count",
        )}
    )


def _compliance(values) -> PendingItemComplianceSummary:
    return PendingItemComplianceSummary(
        **{name: int(values[name]) for name in (
            "en_plazo_count", "atrasado_count", "con_adelanto_count",
            "a_tiempo_count", "con_retraso_count",
        )}
    )


def _average(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_pending_item_report(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    local_date: date,
    planned_from: date | None = None,
    planned_to: date | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    state: PendingItemState | None = None,
    compliance: PendingItemCompliance | None = None,
) -> PendingItemReportResponse:
    if category_id is not None:
        category_exists = db.scalar(
            select(Category.id).where(
                Category.id == category_id,
                Category.workspace_id == workspace_id,
            )
        )
        if category_exists is None:
            raise PendingItemReportCategoryNotFoundError("Category not found")

    filters = _population_filters(
        workspace_id=workspace_id,
        local_date=local_date,
        planned_from=planned_from,
        planned_to=planned_to,
        category_id=category_id,
        is_active=is_active,
        state=state,
        compliance=compliance,
    )
    summary_values = db.execute(
        select(*_aggregate_columns(local_date, include_detail=True))
        .select_from(PendingItem)
        .where(*filters)
    ).one()._mapping
    category_rows = db.execute(
        select(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            *_aggregate_columns(local_date, include_detail=False),
        )
        .select_from(PendingItem)
        .join(Category, PendingItem.category_id == Category.id)
        .where(*filters)
        .group_by(Category.id, Category.name)
        .order_by(Category.normalized_name, Category.id)
    ).all()

    return PendingItemReportResponse(
        period=PendingItemReportPeriod(
            planned_from=planned_from,
            planned_to=planned_to,
        ),
        filters=PendingItemReportFilters(
            category_id=category_id,
            is_active=is_active,
            state=state,
            compliance=compliance,
        ),
        summary=_summary(summary_values),
        compliance=_compliance(summary_values),
        detail=PendingItemDetailSummary(
            average_atrasado_days=_average(summary_values["average_atrasado_days"]),
            average_con_adelanto_days=_average(summary_values["average_con_adelanto_days"]),
            average_con_retraso_days=_average(summary_values["average_con_retraso_days"]),
        ),
        by_category=[
            PendingItemCategoryReportRow(
                category_id=row._mapping["category_id"],
                category_name=row._mapping["category_name"],
                summary=_summary(row._mapping),
                compliance=_compliance(row._mapping),
            )
            for row in category_rows
        ],
    )
