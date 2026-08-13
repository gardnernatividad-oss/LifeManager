import uuid

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import Category, MasterTask
from app.services.task_report_service import (
    TaskReportCategoryNotFoundError,
    TaskReportMasterTaskNotFoundError,
    _completion_rate,
    get_task_report,
)


def _row(**values):
    return SimpleNamespace(_mapping=values)


def test_completion_rate_is_decimal_percent_and_zero_terminal_is_null() -> None:
    assert _completion_rate(2, 3) == Decimal("66.67")
    assert _completion_rate(0, 0) is None


def test_report_summary_and_master_breakdown_use_terminal_outcomes() -> None:
    workspace_id = uuid.uuid4(); master_id = uuid.uuid4(); category_id = uuid.uuid4()
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(completed_count=3, not_completed_count=1))),
        MagicMock(all=MagicMock(return_value=[_row(
            master_task_id=master_id, master_task_name="Salir a correr",
            category_id=category_id, category_name="Salud",
            completed_count=2, not_completed_count=1,
        )])),
    ]
    report = get_task_report(
        db, workspace_id=workspace_id,
        planned_from=date(2026, 8, 4), planned_to=date(2026, 8, 15),
    )
    assert report.summary.completed_count == 3
    assert report.summary.not_completed_count == 1
    assert report.summary.terminal_count == 4
    assert report.summary.completion_rate == Decimal("75.00")
    row = report.by_master_task[0]
    assert row.master_task_name == "Salir a correr" and row.category_name == "Salud"
    assert row.terminal_count == 3 and row.completion_rate == Decimal("66.67")
    summary_sql = str(db.execute.call_args_list[0].args[0])
    breakdown_sql = str(db.execute.call_args_list[1].args[0])
    assert "tasks.result" in summary_sql and "FILTER" in summary_sql
    assert "tasks.planned_date >=" in summary_sql and "tasks.planned_date <=" in summary_sql
    assert "tasks.resolved_at" not in summary_sql
    assert "GROUP BY" in breakdown_sql
    assert "tasks.result IN" in breakdown_sql
    assert workspace_id in db.execute.call_args_list[0].args[0].compile().params.values()
    db.add.assert_not_called(); db.flush.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_zero_terminal_summary_and_unresolved_only_breakdown_are_empty() -> None:
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(completed_count=0, not_completed_count=0))),
        MagicMock(all=MagicMock(return_value=[])),
    ]
    report = get_task_report(db, workspace_id=uuid.uuid4())
    assert report.summary.terminal_count == 0
    assert report.summary.completion_rate is None
    assert report.by_master_task == []
    assert report.period.planned_from is report.period.planned_to is None


def test_master_and_category_filters_are_validated_and_compatible() -> None:
    workspace_id = uuid.uuid4(); category_id = uuid.uuid4()
    master = MasterTask(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category_id,
        name="Correr", normalized_name="correr",
    )
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [master, category_id]
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(completed_count=0, not_completed_count=0))),
        MagicMock(all=MagicMock(return_value=[])),
    ]
    get_task_report(
        db, workspace_id=workspace_id,
        master_task_id=master.id, category_id=category_id,
    )
    for call in db.scalar.call_args_list:
        assert workspace_id in call.args[0].compile().params.values()

    db = MagicMock(spec=Session); db.scalar.return_value = None
    with pytest.raises(TaskReportMasterTaskNotFoundError):
        get_task_report(db, workspace_id=workspace_id, master_task_id=uuid.uuid4())
    db.execute.assert_not_called()

    db = MagicMock(spec=Session); db.scalar.return_value = None
    with pytest.raises(TaskReportCategoryNotFoundError):
        get_task_report(db, workspace_id=workspace_id, category_id=uuid.uuid4())
    db.execute.assert_not_called()

    db = MagicMock(spec=Session)
    other_category = uuid.uuid4(); db.scalar.side_effect = [master, other_category]
    with pytest.raises(TaskReportMasterTaskNotFoundError):
        get_task_report(
            db, workspace_id=workspace_id,
            master_task_id=master.id, category_id=other_category,
        )
    db.execute.assert_not_called()


def test_category_filter_uses_aggregate_join_without_query_loop() -> None:
    workspace_id = uuid.uuid4(); category_id = uuid.uuid4()
    db = MagicMock(spec=Session); db.scalar.return_value = category_id
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(completed_count=1, not_completed_count=0))),
        MagicMock(all=MagicMock(return_value=[])),
    ]
    get_task_report(db, workspace_id=workspace_id, category_id=category_id)
    assert db.execute.call_count == 2
    assert "JOIN master_tasks" in str(db.execute.call_args_list[0].args[0])

