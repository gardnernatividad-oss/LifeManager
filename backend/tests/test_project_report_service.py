import uuid

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.schemas.project import ProjectState
from app.services.project_report_service import (
    ProjectReportCategoryNotFoundError,
    get_project_report,
)


def _row(**values):
    return SimpleNamespace(_mapping=values)


def _summary(**overrides):
    values = {
        "total_count": 0,
        "active_count": 0,
        "inactive_count": 0,
        "no_iniciado_count": 0,
        "en_proceso_count": 0,
        "finalizado_count": 0,
    }
    values.update(overrides)
    return values


def _steps(**overrides):
    values = {
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


def _db(summary, projects=(), steps=None):
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(**summary))),
        MagicMock(all=MagicMock(return_value=list(projects))),
        MagicMock(one=MagicMock(return_value=_row(**(steps or _steps())))),
    ]
    return db


def test_report_returns_project_summary_weighted_rows_and_step_analytics() -> None:
    project_id = uuid.uuid4()
    category_id = uuid.uuid4()
    db = _db(
        _summary(
            total_count=4,
            active_count=3,
            inactive_count=1,
            no_iniciado_count=1,
            en_proceso_count=1,
            finalizado_count=1,
        ),
        [
            _row(
                project_id=project_id,
                project_name="Mudanza",
                category_id=category_id,
                category_name="Personal",
                is_active=True,
                planned_date=date(2026, 8, 20),
                progress=Decimal("62.50"),
                state=ProjectState.EN_PROCESO.value,
                step_count=2,
            )
        ],
        _steps(
            en_plazo_count=1,
            atrasado_count=2,
            con_adelanto_count=1,
            a_tiempo_count=1,
            con_retraso_count=1,
            average_atrasado_days=Decimal("3.125"),
            average_con_adelanto_days=Decimal("2"),
            average_con_retraso_days=Decimal("4.5"),
        ),
    )

    report = get_project_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        planned_from=date(2026, 8, 4),
        planned_to=date(2026, 8, 15),
    )

    assert report.summary.model_dump() == _summary(
        total_count=4,
        active_count=3,
        inactive_count=1,
        no_iniciado_count=1,
        en_proceso_count=1,
        finalizado_count=1,
    )
    row = report.by_project[0]
    assert row.project_id == project_id
    assert row.category_id == category_id
    assert row.planned_date == date(2026, 8, 20)
    assert row.progress == Decimal("62.50")
    assert row.state is ProjectState.EN_PROCESO
    assert report.step_compliance.atrasado_count == 2
    assert report.detail.average_atrasado_days == Decimal("3.13")
    assert report.detail.average_con_adelanto_days == Decimal("2.00")
    assert report.detail.average_con_retraso_days == Decimal("4.50")

    sql = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
    assert "max(project_steps.planned_date)" in sql.lower()
    assert "sum(project_steps.weight * project_steps.progress)" in sql.lower()
    assert "project_report_population" in sql
    assert "project_steps.completion_date" in sql
    assert "avg(" in sql.lower()
    assert "project_steps.name" not in sql
    assert "projects.updated_at" not in sql
    assert "projects.last_tracking_saved_at" not in sql
    assert db.execute.call_count == 3
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()


def test_incomplete_project_counts_in_population_but_not_state_buckets() -> None:
    db = _db(
        _summary(
            total_count=1,
            inactive_count=1,
        ),
        [
            _row(
                project_id=uuid.uuid4(),
                project_name="Borrador",
                category_id=uuid.uuid4(),
                category_name="Personal",
                is_active=False,
                planned_date=None,
                progress=None,
                state=None,
                step_count=0,
            )
        ],
    )
    report = get_project_report(
        db, workspace_id=uuid.uuid4(), local_date=date(2026, 8, 12)
    )
    assert report.summary.total_count == 1
    assert report.summary.no_iniciado_count == 0
    assert report.summary.en_proceso_count == 0
    assert report.summary.finalizado_count == 0
    assert report.by_project[0].planned_date is None
    assert report.by_project[0].progress is None
    assert report.by_project[0].state is None


@pytest.mark.parametrize(
    ("state", "value"),
    [
        (ProjectState.NO_INICIADO, "NO_INICIADO"),
        (ProjectState.EN_PROCESO, "EN_PROCESO"),
        (ProjectState.FINALIZADO, "FINALIZADO"),
    ],
)
def test_derived_state_filters_are_applied_to_aggregated_project_population(
    state: ProjectState, value: str
) -> None:
    db = _db(_summary())
    get_project_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        state=state,
    )
    sql = str(db.execute.call_args_list[0].args[0])
    assert "project_report_metrics.state =" in sql
    assert value in db.execute.call_args_list[0].args[0].compile().params.values()


@pytest.mark.parametrize(
    ("planned_from", "planned_to", "operator"),
    [
        (date(2026, 8, 4), None, "project_report_metrics.planned_date >="),
        (None, date(2026, 8, 15), "project_report_metrics.planned_date <="),
    ],
)
def test_one_sided_period_uses_derived_maximum_step_date(
    planned_from: date | None, planned_to: date | None, operator: str
) -> None:
    db = _db(_summary())
    get_project_report(
        db,
        workspace_id=uuid.uuid4(),
        local_date=date(2026, 8, 12),
        planned_from=planned_from,
        planned_to=planned_to,
    )
    sql = str(db.execute.call_args_list[0].args[0])
    assert "max(project_steps.planned_date)" in sql.lower()
    assert operator in sql


def test_combined_filters_and_category_validation_are_workspace_scoped() -> None:
    workspace_id = uuid.uuid4()
    category_id = uuid.uuid4()
    db = _db(_summary())
    db.scalar.return_value = category_id
    get_project_report(
        db,
        workspace_id=workspace_id,
        local_date=date(2026, 8, 12),
        planned_from=date(2026, 8, 1),
        planned_to=date(2026, 8, 31),
        category_id=category_id,
        is_active=True,
        state=ProjectState.FINALIZADO,
    )
    assert workspace_id in db.scalar.call_args.args[0].compile().params.values()
    sql = str(db.execute.call_args_list[0].args[0])
    params = db.execute.call_args_list[0].args[0].compile().params.values()
    assert "project_report_metrics.category_id =" in sql
    assert "project_report_metrics.is_active = true" in sql.lower()
    assert workspace_id in params and category_id in params


def test_foreign_category_is_rejected_before_aggregate_queries() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    with pytest.raises(ProjectReportCategoryNotFoundError, match="Category not found"):
        get_project_report(
            db,
            workspace_id=uuid.uuid4(),
            local_date=date(2026, 8, 12),
            category_id=uuid.uuid4(),
        )
    db.execute.assert_not_called()


def test_empty_population_returns_zero_counts_and_null_detail() -> None:
    db = _db(_summary())
    report = get_project_report(
        db, workspace_id=uuid.uuid4(), local_date=date(2026, 8, 12)
    )
    assert report.summary.total_count == 0
    assert report.step_compliance.model_dump() == {
        "en_plazo_count": 0,
        "atrasado_count": 0,
        "con_adelanto_count": 0,
        "a_tiempo_count": 0,
        "con_retraso_count": 0,
    }
    assert report.detail.model_dump() == {
        "average_atrasado_days": None,
        "average_con_adelanto_days": None,
        "average_con_retraso_days": None,
    }
    assert report.by_project == []
