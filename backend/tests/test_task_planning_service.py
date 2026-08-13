import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, MasterTask, Task, TaskResult, User
from app.schemas.master_task import MasterTaskUpdate
from app.schemas.task import (
    BulkTaskPattern,
    TaskBulkCreate,
    TaskBulkDelete,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)
from app.services.master_task_service import MasterTaskInUseError, update_master_task
from app.services.task_service import (
    TaskBulkValidationError,
    TaskMasterTaskNotFoundError,
    TaskNotFoundError,
    TaskOccurrenceConflictError,
    TaskPlanningConflictError,
    TaskVersionConflictError,
    _dates_for_bulk,
    create_task,
    create_tasks_bulk,
    delete_task,
    delete_tasks_bulk,
    list_tasks,
    update_task,
)


def _db() -> MagicMock:
    return MagicMock(spec=Session)


def _domain():
    workspace_id = uuid.uuid4()
    category = Category(id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud")
    master = MasterTask(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Correr", normalized_name="correr",
    )
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    return workspace_id, category, master, user


def _task(workspace_id, master, planned=date(2026, 8, 20), version=1, result=None):
    timestamp = datetime.now(timezone.utc)
    return Task(
        id=uuid.uuid4(), workspace_id=workspace_id, master_task_id=master.id,
        master_task=master, planned_date=planned, result=result, lock_version=version,
        created_at=timestamp, updated_at=timestamp,
    )


def test_individual_creation_is_unresolved_scoped_and_version_one() -> None:
    workspace_id, _category, master, user = _domain()
    db = _db()
    db.scalar.side_effect = [master, None]
    task = create_task(
        db, workspace_id=workspace_id, current_user=user,
        task_in=TaskCreate(master_task_id=master.id, planned_date=date(2026, 8, 20)),
    )
    assert task.workspace_id == workspace_id
    assert task.master_task is master
    assert task.created_by_id == user.id
    assert task.result is task.resolved_at is task.resolved_by_id is None
    assert task.lock_version == 1
    master_lookup = db.scalar.call_args_list[0].args[0]
    assert master_lookup._for_update_arg is not None
    db.add.assert_called_once_with(task)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_individual_creation_rejects_foreign_master_and_duplicate() -> None:
    workspace_id, _category, master, user = _domain()
    db = _db(); db.scalar.return_value = None
    with pytest.raises(TaskMasterTaskNotFoundError):
        create_task(db, workspace_id=workspace_id, current_user=user,
                    task_in=TaskCreate(master_task_id=uuid.uuid4(), planned_date=date(2026, 8, 20)))
    db = _db(); db.scalar.side_effect = [master, uuid.uuid4()]
    with pytest.raises(TaskOccurrenceConflictError):
        create_task(db, workspace_id=workspace_id, current_user=user,
                    task_in=TaskCreate(master_task_id=master.id, planned_date=date(2026, 8, 20)))


def test_bulk_date_generation_daily_and_selected_weekdays() -> None:
    master_id = uuid.uuid4()
    daily = TaskBulkCreate(master_task_id=master_id, start_date=date(2026, 8, 1), end_date=date(2026, 8, 3), pattern="DAILY")
    assert _dates_for_bulk(daily) == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)]
    weekly = TaskBulkCreate(master_task_id=master_id, start_date=date(2026, 8, 1), end_date=date(2026, 8, 10), pattern="WEEKLY", weekdays=[0, 4])
    assert _dates_for_bulk(weekly) == [date(2026, 8, 3), date(2026, 8, 7), date(2026, 8, 10)]


def test_bulk_occurrence_safeguard_is_configurable() -> None:
    request = TaskBulkCreate(master_task_id=uuid.uuid4(), start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), pattern="DAILY")
    with patch("app.services.task_service.settings.TASK_BULK_MAX_OCCURRENCES", 2):
        with pytest.raises(TaskBulkValidationError, match="safeguard"):
            _dates_for_bulk(request)


def test_bulk_creation_prevalidates_conflicts_and_creates_independent_rows() -> None:
    workspace_id, _category, master, user = _domain()
    request = TaskBulkCreate(master_task_id=master.id, start_date=date(2026, 8, 1), end_date=date(2026, 8, 3), pattern="DAILY")
    db = _db(); db.scalar.return_value = master; db.scalars.return_value.all.return_value = []
    tasks = create_tasks_bulk(db, workspace_id=workspace_id, current_user=user, task_in=request)
    assert len(tasks) == 3 and len({id(task) for task in tasks}) == 3
    assert [task.planned_date for task in tasks] == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)]
    db.add_all.assert_called_once_with(tasks)
    db.flush.assert_called_once_with()

    conflict_db = _db(); conflict_db.scalar.return_value = master
    conflict_db.scalars.return_value.all.return_value = [date(2026, 8, 2)]
    with pytest.raises(TaskOccurrenceConflictError):
        create_tasks_bulk(conflict_db, workspace_id=workspace_id, current_user=user, task_in=request)
    conflict_db.add_all.assert_not_called(); conflict_db.flush.assert_not_called()


def test_bulk_unique_race_is_translated_for_router_rollback() -> None:
    workspace_id, _category, master, user = _domain()
    db = _db(); db.scalar.return_value = master; db.scalars.return_value.all.return_value = []
    original = MagicMock(); original.diag.constraint_name = "uq_tasks_workspace_id_master_task_id_planned_date"
    db.flush.side_effect = IntegrityError("insert", {}, original)
    request = TaskBulkCreate(master_task_id=master.id, start_date=date(2026, 8, 1), end_date=date(2026, 8, 1), pattern="DAILY")
    with pytest.raises(TaskOccurrenceConflictError):
        create_tasks_bulk(db, workspace_id=workspace_id, current_user=user, task_in=request)


def test_list_is_filtered_paginated_and_deterministic() -> None:
    workspace_id, category, master, _user = _domain()
    db = _db(); db.scalar.side_effect = [master, category.id, 1]
    row = _task(workspace_id, master); db.scalars.return_value.all.return_value = [row]
    items, total = list_tasks(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12), page=2, page_size=25,
        planned_from=date(2026, 8, 1), planned_to=date(2026, 8, 31),
        master_task_id=master.id, category_id=category.id, status=TaskStatus.PROGRAMADA,
    )
    assert items == [row] and total == 1
    statement = db.scalars.call_args.args[0]
    assert statement._offset_clause.value == 25 and statement._limit_clause.value == 25
    assert workspace_id in statement.compile().params.values()
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_scheduled_update_increments_version_and_can_become_pending() -> None:
    workspace_id, _category, master, _user = _domain()
    task = _task(workspace_id, master, version=3)
    db = _db(); db.scalar.return_value = task; db.execute.return_value.rowcount = 1
    result = update_task(
        db, workspace_id=workspace_id, task_id=task.id,
        task_in=TaskUpdate(planned_date=date(2026, 8, 12), lock_version=3),
        local_date=date(2026, 8, 12),
    )
    assert result.planned_date == date(2026, 8, 12) and result.lock_version == 4
    state = inspect(result)
    assert state.attrs.planned_date.history.has_changes() is False
    assert state.attrs.lock_version.history.has_changes() is False
    update_statement = db.execute.call_args.args[0]
    compiled_parameters = update_statement.compile().params.values()
    assert task.id in compiled_parameters
    assert workspace_id in compiled_parameters
    assert 3 in compiled_parameters
    db.flush.assert_called_once_with(); db.commit.assert_not_called()


@pytest.mark.parametrize("planned,result", [(date(2026, 8, 12), None), (date(2026, 8, 1), None), (date(2026, 8, 20), TaskResult.COMPLETED)])
def test_non_scheduled_task_cannot_be_edited_or_deleted(planned, result) -> None:
    workspace_id, _category, master, _user = _domain()
    task = _task(workspace_id, master, planned=planned, result=result)
    db = _db(); db.scalar.return_value = task
    with pytest.raises(TaskPlanningConflictError):
        update_task(db, workspace_id=workspace_id, task_id=task.id,
                    task_in=TaskUpdate(planned_date=date(2026, 8, 21), lock_version=1), local_date=date(2026, 8, 12))
    with pytest.raises(TaskPlanningConflictError):
        delete_task(db, workspace_id=workspace_id, task_id=task.id, lock_version=1, local_date=date(2026, 8, 12))


def test_stale_update_and_delete_are_rejected() -> None:
    workspace_id, _category, master, _user = _domain()
    task = _task(workspace_id, master, version=2)
    db = _db(); db.scalar.return_value = task; db.execute.return_value.rowcount = 0
    with pytest.raises(TaskVersionConflictError):
        update_task(db, workspace_id=workspace_id, task_id=task.id,
                    task_in=TaskUpdate(planned_date=date(2026, 8, 21), lock_version=1), local_date=date(2026, 8, 12))
    with pytest.raises(TaskVersionConflictError):
        delete_task(db, workspace_id=workspace_id, task_id=task.id, lock_version=1, local_date=date(2026, 8, 12))


def test_bulk_delete_validates_every_row_before_deleting() -> None:
    workspace_id, _category, master, _user = _domain()
    tasks = [_task(workspace_id, master), _task(workspace_id, master)]
    request = TaskBulkDelete(items=[{"id": task.id, "lock_version": 1} for task in tasks])
    db = _db(); db.scalars.return_value.all.return_value = tasks
    assert delete_tasks_bulk(db, workspace_id=workspace_id, task_in=request, local_date=date(2026, 8, 12)) == 2
    assert db.delete.call_count == 2; db.flush.assert_called_once_with()

    invalid_db = _db(); tasks[1].planned_date = date(2026, 8, 12)
    invalid_db.scalars.return_value.all.return_value = tasks
    with pytest.raises(TaskPlanningConflictError):
        delete_tasks_bulk(invalid_db, workspace_id=workspace_id, task_in=request, local_date=date(2026, 8, 12))
    invalid_db.delete.assert_not_called(); invalid_db.flush.assert_not_called()


def test_foreign_task_in_bulk_aborts_without_delete() -> None:
    workspace_id, _category, master, _user = _domain()
    task_id = uuid.uuid4(); db = _db(); db.scalars.return_value.all.return_value = []
    with pytest.raises(TaskNotFoundError):
        delete_tasks_bulk(db, workspace_id=workspace_id,
                          task_in=TaskBulkDelete(items=[{"id": task_id, "lock_version": 1}]), local_date=date(2026, 8, 12))
    db.delete.assert_not_called()


def test_first_occurrence_makes_master_task_immutable() -> None:
    workspace_id, _category, master, _user = _domain()
    db = _db(); db.scalar.side_effect = [master, True]
    with pytest.raises(MasterTaskInUseError):
        update_master_task(db, workspace_id=workspace_id, master_task_id=master.id,
                           master_task_in=MasterTaskUpdate(name="Nuevo"))
