import uuid

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.schemas.pending_item import PendingItemCompliance, PendingItemState
from app.services.pending_item_report_service import (
    PendingItemReportCategoryNotFoundError,
    get_pending_item_report,
)


def _row(**values):
    return SimpleNamespace(_mapping=values)


def _metrics(**overrides):
    values = {
        "total_count": 0,
        "active_count": 0,
        "inactive_count": 0,
        "no_iniciado_count": 0,
        "en_proceso_count": 0,
        "finalizado_count": 0,
        "en_plazo_count": 0,
        "atrasado_count": 0,
        "con_adelanto_count": 0,
        "a_tiempo_count": 0,
        "con_retraso_count": 0,
        "average_atrasado_days": None,
        "average_con_adelanto_days": None,
        "average_con_retraso_days": None,
    }
    values.update(overrides)
    return values


def _db(summary, categories=()):
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(**summary))),
        MagicMock(all=MagicMock(return_value=list(categories))),
    ]
    return db


def test_report_derives_state_compliance_detail_and_category_aggregates() -> None:
    category_id = uuid.uuid4()
    db = _db(
        _metrics(
            total_count=8,
            active_count=7,
            inactive_count=1,
            no_iniciado_count=2,
            en_proceso_count=3,
            finalizado_count=3,
            en_plazo_count=1,
            atrasado_count=3,
            con_adelanto_count=1,
            a_tiempo_count=1,
            con_retraso_count=1,
            average_atrasado_days=Decimal("2.125"),
            average_con_adelanto_days=Decimal("4"),
            average_con_retraso_days=Decimal("1.5"),
        ),
        [_row(category_id=category_id, category_name="Salud", **_metrics(
            total_count=3, active_count=3, no_iniciado_count=1,
            en_proceso_count=1, finalizado_count=1, en_plazo_count=1,
            atrasado_count=1, a_tiempo_count=1,
        ))],
    )

    report = get_pending_item_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        planned_from=date(2026, 8, 1),
        planned_to=date(2026, 8, 31),
    )

    assert report.summary.model_dump() == {
        "total_count": 8,
        "active_count": 7,
        "inactive_count": 1,
        "no_iniciado_count": 2,
        "en_proceso_count": 3,
        "finalizado_count": 3,
    }
    assert report.compliance.model_dump() == {
        "en_plazo_count": 1,
        "atrasado_count": 3,
        "con_adelanto_count": 1,
        "a_tiempo_count": 1,
        "con_retraso_count": 1,
    }
    assert report.detail.average_atrasado_days == Decimal("2.13")
    assert report.detail.average_con_adelanto_days == Decimal("4.00")
    assert report.detail.average_con_retraso_days == Decimal("1.50")
    assert report.by_category[0].category_id == category_id
    assert report.by_category[0].summary.total_count == 3
    assert report.by_category[0].compliance.atrasado_count == 1

    summary_sql = str(db.execute.call_args_list[0].args[0])
    category_sql = str(db.execute.call_args_list[1].args[0])
    assert "pending_items.planned_date >=" in summary_sql
    assert "pending_items.planned_date <=" in summary_sql
    assert "pending_items.progress" in summary_sql
    assert "pending_items.completion_date" in summary_sql
    assert "avg(" in summary_sql.lower()
    assert "GROUP BY categories.id, categories.name" in category_sql
    assert "pending_items.name" not in category_sql
    assert db.execute.call_count == 2
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (PendingItemState.NO_INICIADO, "pending_items.progress ="),
        (PendingItemState.EN_PROCESO, "pending_items.progress BETWEEN"),
        (PendingItemState.FINALIZADO, "pending_items.progress ="),
    ],
)
def test_state_filters_are_applied_in_sql(state, expected) -> None:
    db = _db(_metrics())
    get_pending_item_report(
        db, workspace_id=uuid.uuid4(), local_date=date(2026, 8, 12), state=state
    )
    assert expected in str(db.execute.call_args_list[0].args[0])


@pytest.mark.parametrize(
    ("planned_from", "planned_to", "included", "excluded"),
    [
        (date(2026, 8, 1), None, "planned_date >=", "planned_date <="),
        (None, date(2026, 8, 31), "planned_date <=", "planned_date >="),
    ],
)
def test_one_sided_period_filters_use_planned_date_only(
    planned_from: date | None,
    planned_to: date | None,
    included: str,
    excluded: str,
) -> None:
    db = _db(_metrics())
    get_pending_item_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        planned_from=planned_from,
        planned_to=planned_to,
    )
    statement = db.execute.call_args_list[0].args[0]
    where_sql = " ".join(str(clause) for clause in statement._where_criteria)
    assert f"pending_items.{included}" in where_sql
    assert f"pending_items.{excluded}" not in where_sql
    assert "pending_items.updated_at" not in where_sql


@pytest.mark.parametrize("compliance", list(PendingItemCompliance))
def test_each_compliance_filter_is_applied_in_sql_and_excludes_null_dates(
    compliance: PendingItemCompliance,
) -> None:
    db = _db(_metrics())
    get_pending_item_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        compliance=compliance,
    )
    sql = str(db.execute.call_args_list[0].args[0])
    assert "pending_items.planned_date IS NOT NULL" in sql
    assert "pending_items.completion_date" in sql


def test_filters_define_population_and_remain_workspace_scoped() -> None:
    workspace_id = uuid.uuid4()
    category_id = uuid.uuid4()
    db = _db(_metrics())
    db.scalar.return_value = category_id
    get_pending_item_report(
        db,
        workspace_id=workspace_id,
        local_date=date(2026, 8, 12),
        planned_from=date(2026, 8, 1),
        category_id=category_id,
        is_active=False,
        state=PendingItemState.FINALIZADO,
        compliance=PendingItemCompliance.CON_RETRASO,
    )
    validation_params = db.scalar.call_args.args[0].compile().params.values()
    assert workspace_id in validation_params and category_id in validation_params
    for call in db.execute.call_args_list:
        params = call.args[0].compile().params.values()
        assert workspace_id in params and category_id in params
    report_filter = str(db.execute.call_args_list[0].args[0])
    assert "pending_items.is_active = false" in report_filter.lower()
    assert "pending_items.planned_date >=" in report_filter


def test_foreign_or_missing_category_is_safe_not_found_before_aggregates() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    with pytest.raises(PendingItemReportCategoryNotFoundError, match="Category not found"):
        get_pending_item_report(
            db,
            workspace_id=uuid.uuid4(),
            local_date=date(2026, 8, 12),
            category_id=uuid.uuid4(),
        )
    db.execute.assert_not_called()


def test_empty_population_has_zero_counts_and_null_detail_averages() -> None:
    db = _db(_metrics())
    report = get_pending_item_report(
        db, workspace_id=uuid.uuid4(), local_date=date(2026, 8, 12)
    )
    assert report.summary.total_count == 0
    assert report.detail.model_dump() == {
        "average_atrasado_days": None,
        "average_con_adelanto_days": None,
        "average_con_retraso_days": None,
    }
    assert report.by_category == []
