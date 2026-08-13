import uuid

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.models import WorkspaceTrackingMetadata
from app.services.home_service import get_home_summary


def _row(**values):
    return SimpleNamespace(_mapping=values)


def test_home_uses_workspace_scoped_aggregate_queries_and_metadata() -> None:
    workspace_id = uuid.uuid4()
    metadata = WorkspaceTrackingMetadata(
        workspace_id=workspace_id,
        last_review_saved_at=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
        pending_items_last_tracking_saved_at=datetime(
            2026, 8, 10, 20, tzinfo=timezone.utc
        ),
    )
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(due_today=2, overdue=3))),
        MagicMock(one=MagicMock(return_value=_row(overdue=4))),
        MagicMock(one=MagicMock(return_value=_row(overdue=5))),
    ]
    db.get.return_value = metadata

    result = get_home_summary(
        db,
        workspace_id=workspace_id,
        user_first_name="Ana",
        local_date=date(2026, 8, 12),
    )

    assert result.user_first_name == "Ana"
    assert result.local_date == date(2026, 8, 12)
    assert result.tasks.due_today == 2 and result.tasks.overdue == 3
    assert result.pending_items.overdue == 4
    assert result.project_steps.overdue == 5
    assert result.last_review_saved_at == metadata.last_review_saved_at
    assert (
        result.pending_items_last_tracking_saved_at
        == metadata.pending_items_last_tracking_saved_at
    )
    for call in db.execute.call_args_list:
        statement = call.args[0]
        assert workspace_id in statement.compile().params.values()
    assert "JOIN projects" in str(db.execute.call_args_list[2].args[0])
    db.get.assert_called_once_with(WorkspaceTrackingMetadata, workspace_id)
    db.add.assert_not_called(); db.flush.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_home_without_metadata_returns_null_timestamps() -> None:
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(due_today=0, overdue=0))),
        MagicMock(one=MagicMock(return_value=_row(overdue=0))),
        MagicMock(one=MagicMock(return_value=_row(overdue=0))),
    ]
    db.get.return_value = None
    result = get_home_summary(
        db,
        workspace_id=uuid.uuid4(),
        user_first_name="Ana",
        local_date=date(2026, 8, 12),
    )
    assert result.last_review_saved_at is None
    assert result.pending_items_last_tracking_saved_at is None


def test_home_queries_encode_only_approved_attention_semantics() -> None:
    workspace_id = uuid.uuid4(); local_date = date(2026, 8, 12)
    db = MagicMock(spec=Session)
    db.execute.side_effect = [
        MagicMock(one=MagicMock(return_value=_row(due_today=0, overdue=0))),
        MagicMock(one=MagicMock(return_value=_row(overdue=0))),
        MagicMock(one=MagicMock(return_value=_row(overdue=0))),
    ]
    get_home_summary(
        db, workspace_id=workspace_id, user_first_name="Ana", local_date=local_date
    )
    task_sql = str(db.execute.call_args_list[0].args[0])
    pending_sql = str(db.execute.call_args_list[1].args[0])
    step_sql = str(db.execute.call_args_list[2].args[0])
    assert "tasks.result IS NULL" in task_sql
    assert "tasks.planned_date =" in task_sql and "tasks.planned_date <" in task_sql
    assert "pending_items.is_active IS true" in pending_sql
    assert "pending_items.progress <" in pending_sql
    assert "projects.is_active IS true" in step_sql
    assert "project_steps.progress <" in step_sql

