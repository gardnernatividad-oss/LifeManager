import uuid

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import Category, MasterTask, Task, TaskResult, User
from app.schemas.task import TaskResultUpdate, TaskStatus, derive_task_status
from app.services.task_service import (
    TaskNotFoundError,
    TaskResultConflictError,
    TaskVersionConflictError,
    set_task_result,
    list_tasks,
)


def _domain(
    *,
    planned_date: date = date(2026, 8, 12),
    result: TaskResult | None = None,
    lock_version: int = 1,
    resolved_at: datetime | None = None,
) -> tuple[uuid.UUID, User, Task]:
    workspace_id = uuid.uuid4()
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud"
    )
    master_task = MasterTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name="Correr",
        normalized_name="correr",
    )
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    task = Task(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        master_task_id=master_task.id,
        master_task=master_task,
        planned_date=planned_date,
        result=result,
        resolved_at=resolved_at,
        resolved_by_id=user.id if result is not None else None,
        lock_version=lock_version,
    )
    return workspace_id, user, task


@pytest.mark.parametrize(
    ("target", "expected_status"),
    [
        (TaskResult.COMPLETED, TaskStatus.COMPLETADA),
        (TaskResult.NOT_COMPLETED, TaskStatus.NO_REALIZADA),
    ],
)
def test_pending_task_receives_terminal_result(target, expected_status) -> None:
    workspace_id, user, task = _domain()
    db = MagicMock(spec=Session)
    db.scalar.return_value = task
    db.execute.return_value.rowcount = 1
    timestamp = datetime(2026, 8, 12, 20, 30, tzinfo=timezone.utc)

    updated = set_task_result(
        db,
        workspace_id=workspace_id,
        task_id=task.id,
        current_user=user,
        result_in=TaskResultUpdate(result=target, lock_version=1),
        local_date=date(2026, 8, 12),
        resolved_at=timestamp,
    )

    assert updated.result is target
    assert updated.resolved_at == timestamp
    assert updated.resolved_by_id == user.id
    assert updated.lock_version == 2
    assert derive_task_status(updated, local_date=date(2026, 8, 12)) is expected_status
    state = inspect(updated)
    for field in ("result", "resolved_at", "resolved_by_id", "lock_version"):
        assert state.attrs[field].history.has_changes() is False
    db.execute.assert_called_once()
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("original", "target"),
    [
        (TaskResult.COMPLETED, TaskResult.NOT_COMPLETED),
        (TaskResult.NOT_COMPLETED, TaskResult.COMPLETED),
    ],
)
def test_terminal_result_correction_replaces_timestamp_and_actor(original, target) -> None:
    old_timestamp = datetime(2026, 8, 12, 10, tzinfo=timezone.utc)
    workspace_id, user, task = _domain(
        result=original, lock_version=4, resolved_at=old_timestamp
    )
    correcting_user = User(id=uuid.uuid4(), timezone="America/Lima")
    db = MagicMock(spec=Session)
    db.scalar.return_value = task
    db.execute.return_value.rowcount = 1
    correction_time = old_timestamp + timedelta(hours=2)

    updated = set_task_result(
        db,
        workspace_id=workspace_id,
        task_id=task.id,
        current_user=correcting_user,
        result_in=TaskResultUpdate(result=target, lock_version=4),
        local_date=date(2026, 8, 12),
        resolved_at=correction_time,
    )

    assert updated.result is target
    assert updated.resolved_at == correction_time
    assert updated.resolved_at != old_timestamp
    assert updated.resolved_by_id == correcting_user.id
    assert updated.lock_version == 5


def test_scheduled_task_cannot_receive_result() -> None:
    workspace_id, user, task = _domain(planned_date=date(2026, 8, 13))
    db = MagicMock(spec=Session)
    db.scalar.return_value = task

    with pytest.raises(TaskResultConflictError, match="Scheduled"):
        set_task_result(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            current_user=user,
            result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=1),
            local_date=date(2026, 8, 12),
        )

    db.execute.assert_not_called()
    db.flush.assert_not_called()


def test_same_terminal_result_is_not_a_correction() -> None:
    workspace_id, user, task = _domain(
        result=TaskResult.COMPLETED,
        resolved_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    db = MagicMock(spec=Session)
    db.scalar.return_value = task
    with pytest.raises(TaskResultConflictError, match="already has"):
        set_task_result(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            current_user=user,
            result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=1),
            local_date=date(2026, 8, 12),
        )


def test_stale_result_update_fails_before_write_and_cas_race_returns_conflict() -> None:
    workspace_id, user, task = _domain(lock_version=2)
    db = MagicMock(spec=Session)
    db.scalar.return_value = task
    with pytest.raises(TaskVersionConflictError):
        set_task_result(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            current_user=user,
            result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=1),
            local_date=date(2026, 8, 12),
        )
    db.execute.assert_not_called()

    task.lock_version = 2
    db.execute.return_value.rowcount = 0
    with pytest.raises(TaskVersionConflictError):
        set_task_result(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            current_user=user,
            result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=2),
            local_date=date(2026, 8, 12),
        )
    db.flush.assert_not_called()


def test_result_cas_is_workspace_version_and_state_qualified() -> None:
    workspace_id, user, task = _domain(lock_version=3)
    db = MagicMock(spec=Session)
    db.scalar.return_value = task
    db.execute.return_value.rowcount = 1
    set_task_result(
        db,
        workspace_id=workspace_id,
        task_id=task.id,
        current_user=user,
        result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=3),
        local_date=date(2026, 8, 12),
    )
    statement = db.execute.call_args.args[0]
    values = list(statement.compile().params.values())
    assert task.id in values
    assert workspace_id in values
    assert 3 in values
    assert statement._where_criteria


def test_foreign_workspace_task_is_not_exposed() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    with pytest.raises(TaskNotFoundError):
        set_task_result(
            db,
            workspace_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            current_user=User(id=uuid.uuid4(), timezone="America/Lima"),
            result_in=TaskResultUpdate(result=TaskResult.COMPLETED, lock_version=1),
            local_date=date(2026, 8, 12),
        )
    lookup = db.scalar.call_args.args[0]
    assert len(lookup.compile().params) == 2


@pytest.mark.parametrize(
    ("status", "database_result"),
    [
        (TaskStatus.COMPLETADA, TaskResult.COMPLETED),
        (TaskStatus.NO_REALIZADA, TaskResult.NOT_COMPLETED),
    ],
)
def test_tracking_terminal_status_filters_execute_in_database(status, database_result) -> None:
    workspace_id = uuid.uuid4()
    db = MagicMock(spec=Session)
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []

    items, total = list_tasks(
        db,
        workspace_id=workspace_id,
        local_date=date(2026, 8, 12),
        page=1,
        page_size=25,
        status=status,
    )

    assert items == [] and total == 0
    count_statement = db.scalar.call_args.args[0]
    assert database_result in count_statement.compile().params.values()
    db.commit.assert_not_called()
