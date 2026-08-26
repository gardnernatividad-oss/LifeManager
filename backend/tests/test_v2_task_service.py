import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import Category, MasterTask, Task, User, Workspace, WorkspaceMember
from app.models.enums import TaskResult, WorkspaceKind
from app.schemas.v2_task import RecurringTaskCreate, TaskCreate, TaskUpdate
from app.services.v2_task import MAX_RECURRING_TASK_OCCURRENCES, TaskConflictError, TaskPermissionError, TaskRecurrenceError, _mutation_scope_tasks, create_recurring_tasks, create_task, delete_task, resolve_task, task_projection, update_task
from app.services.v2_workspace import WorkspaceAccess


def _context(kind: WorkspaceKind = WorkspaceKind.SHARED):
    actor = User(id=uuid.uuid4(), email="member@example.com", hashed_password="hash", first_name="Ana", last_name="Uno")
    workspace = Workspace(id=uuid.uuid4(), name="Casa", kind=kind, owner_user_id=actor.id)
    membership = WorkspaceMember(workspace_id=workspace.id, user_id=actor.id)
    return actor, WorkspaceAccess(workspace=workspace, membership=membership)


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
def test_create_uses_context_and_never_commits(master, responsible) -> None:
    actor, access = _context()
    db = MagicMock()
    selected = uuid.uuid4()
    task = create_task(db, access=access, actor=actor, task_in=TaskCreate(master_task_id=uuid.uuid4(), planned_date=date(2026, 9, 1), responsible_user_id=selected))
    assert task.workspace_id == access.workspace.id
    assert task.responsible_user_id == selected
    assert task.created_by_user_id == actor.id
    assert task.generation_batch_id is None
    master.assert_called_once()
    responsible.assert_called_once_with(db, workspace_id=access.workspace.id, user_id=selected)
    db.add.assert_called_once_with(task)
    db.flush.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
def test_personal_creation_derives_owner(master, responsible) -> None:
    actor, access = _context(WorkspaceKind.PERSONAL)
    foreign = uuid.uuid4()
    task = create_task(db := MagicMock(), access=access, actor=actor, task_in=TaskCreate(master_task_id=uuid.uuid4(), planned_date=date(2026, 9, 1), responsible_user_id=foreign))
    assert task.responsible_user_id == actor.id
    responsible.assert_called_once_with(db, workspace_id=access.workspace.id, user_id=actor.id)


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
@patch("app.services.v2_task._task")
def test_update_changes_only_allowed_fields_and_checks_version(task_lookup, master, responsible) -> None:
    _, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 1), lock_version=2)
    original_id = task.id
    task_lookup.return_value = task
    target = uuid.uuid4()
    updated = update_task(db := MagicMock(), access=access, task_id=task.id, task_in=TaskUpdate(responsible_user_id=target, lock_version=2), local_date=date(2026, 8, 31))
    assert updated.id == original_id
    assert updated.responsible_user_id == target
    assert updated.planned_date == date(2026, 9, 1)
    assert updated.lock_version == 3
    responsible.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_not_called()


@pytest.mark.parametrize("planned_date", [date(2026, 9, 1), date(2026, 8, 31)])
@pytest.mark.parametrize(
    "task_in",
    [
        TaskUpdate(planned_date=date(2026, 9, 10), lock_version=1),
        TaskUpdate(responsible_user_id=uuid.uuid4(), lock_version=1),
        TaskUpdate(master_task_id=uuid.uuid4(), lock_version=1),
    ],
)
@patch("app.services.v2_task._task")
def test_today_and_overdue_unresolved_tasks_cannot_be_edited(task_lookup, task_in, planned_date) -> None:
    _, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=planned_date, lock_version=1)
    task_lookup.return_value = task
    db = MagicMock()
    with pytest.raises(TaskConflictError):
        update_task(db, access=access, task_id=task.id, task_in=task_in, local_date=date(2026, 9, 1))
    db.flush.assert_not_called()
    assert task.planned_date == planned_date


@patch("app.services.v2_task._task")
def test_only_current_responsible_can_resolve_once(task_lookup) -> None:
    actor, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=actor.id, planned_date=date(2026, 9, 1), lock_version=1)
    task_lookup.return_value = task
    with pytest.raises(TaskPermissionError):
        resolve_task(MagicMock(), access=access, actor=actor, task_id=task.id, expected_version=1, result=TaskResult.COMPLETED, local_date=date(2026, 9, 1))
    task.responsible_user_id = actor.id
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = resolve_task(db := MagicMock(), access=access, actor=actor, task_id=task.id, expected_version=1, result=TaskResult.NOT_COMPLETED, local_date=date(2026, 9, 1), now=now)
    assert result.result == TaskResult.NOT_COMPLETED
    assert result.resolved_at == now
    assert result.resolved_by_user_id == actor.id
    with pytest.raises(TaskConflictError):
        resolve_task(db, access=access, actor=actor, task_id=task.id, expected_version=2, result=TaskResult.COMPLETED, local_date=date(2026, 9, 1))
    db.commit.assert_not_called()


@patch("app.services.v2_task._task")
def test_delete_only_future_unresolved_standalone(task_lookup) -> None:
    _, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 2), lock_version=1)
    task_lookup.return_value = task
    db = MagicMock()
    delete_task(db, access=access, task_id=task.id, expected_version=1, local_date=date(2026, 9, 1))
    db.delete.assert_called_once_with(task)
    db.flush.assert_called_once()
    task.planned_date = date(2026, 9, 1)
    with pytest.raises(TaskConflictError):
        delete_task(MagicMock(), access=access, task_id=task.id, expected_version=1, local_date=date(2026, 9, 1))


def test_projection_allows_edit_only_while_unresolved_task_is_future() -> None:
    actor, access = _context()
    category = Category(id=uuid.uuid4(), workspace_id=access.workspace.id, name="Casa", normalized_name="casa")
    master = MasterTask(id=uuid.uuid4(), workspace_id=access.workspace.id, category_id=category.id, name="Comprar", normalized_name="comprar")
    master.category = category
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=master.id, responsible_user_id=actor.id, created_by_user_id=actor.id, planned_date=date(2026, 9, 2), lock_version=1)
    task.master_task = master
    db = MagicMock()
    db.scalar.return_value = actor
    _, state, is_generated, can_edit_this, can_edit_future, can_resolve, can_delete_this, can_delete_future = task_projection(db, task=task, actor_id=actor.id, local_date=date(2026, 9, 1))
    assert (state, is_generated, can_edit_this, can_edit_future, can_resolve, can_delete_this, can_delete_future) == ("PROGRAMADA", False, True, False, False, True, False)
    task.planned_date = date(2026, 9, 1)
    _, state, is_generated, can_edit_this, can_edit_future, can_resolve, can_delete_this, can_delete_future = task_projection(db, task=task, actor_id=actor.id, local_date=date(2026, 9, 1))
    assert (state, is_generated, can_edit_this, can_edit_future, can_resolve, can_delete_this, can_delete_future) == ("PENDIENTE", False, False, False, True, False, False)


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
@patch("app.services.v2_task._mutation_scope_tasks")
def test_generated_this_edit_preserves_batch(scope_tasks, master, responsible) -> None:
    _, access = _context()
    batch_id = uuid.uuid4()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 2), generation_batch_id=batch_id, lock_version=1)
    scope_tasks.return_value = (task, [task])
    target_master = uuid.uuid4()
    updated = update_task(db := MagicMock(), access=access, task_id=task.id, task_in=TaskUpdate(master_task_id=target_master, planned_date=date(2026, 9, 3), lock_version=1, scope="THIS"), local_date=date(2026, 9, 1))
    assert updated.master_task_id == target_master
    assert updated.planned_date == date(2026, 9, 3)
    assert updated.generation_batch_id == batch_id
    db.flush.assert_called_once()


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._mutation_scope_tasks")
def test_future_scope_changes_only_locked_future_unresolved_tasks(scope_tasks, responsible) -> None:
    _, access = _context()
    batch_id = uuid.uuid4()
    selected = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=batch_id, lock_version=2)
    later = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 4), generation_batch_id=batch_id, lock_version=4)
    scope_tasks.return_value = (selected, [selected, later])
    target = uuid.uuid4()
    update_task(db := MagicMock(), access=access, task_id=selected.id, task_in=TaskUpdate(responsible_user_id=target, lock_version=2, scope="THIS_AND_FUTURE"), local_date=date(2026, 9, 1))
    assert selected.responsible_user_id == target and later.responsible_user_id == target
    assert (selected.lock_version, later.lock_version) == (3, 5)
    assert selected.generation_batch_id == later.generation_batch_id == batch_id
    db.flush.assert_called_once()


@patch("app.services.v2_task._mutation_scope_tasks")
def test_future_scope_rejects_date_change_before_flush(scope_tasks) -> None:
    _, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=uuid.uuid4(), lock_version=1)
    scope_tasks.return_value = (task, [task])
    db = MagicMock()
    with pytest.raises(TaskConflictError):
        update_task(db, access=access, task_id=task.id, task_in=TaskUpdate(planned_date=date(2026, 9, 4), lock_version=1, scope="THIS_AND_FUTURE"), local_date=date(2026, 9, 1))
    db.flush.assert_not_called()


@patch("app.services.v2_task._mutation_scope_tasks")
def test_this_scope_rejects_moving_occurrence_to_today_or_past(scope_tasks) -> None:
    _, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=uuid.uuid4(), lock_version=1)
    scope_tasks.return_value = (task, [task])
    db = MagicMock()
    with pytest.raises(TaskConflictError):
        update_task(db, access=access, task_id=task.id, task_in=TaskUpdate(planned_date=date(2026, 9, 1), lock_version=1, scope="THIS"), local_date=date(2026, 9, 1))
    db.flush.assert_not_called()


@patch("app.services.v2_task._mutation_scope_tasks")
def test_future_scope_delete_deletes_only_returned_scope(scope_tasks) -> None:
    _, access = _context()
    selected = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=uuid.uuid4(), lock_version=1)
    later = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 4), generation_batch_id=selected.generation_batch_id, lock_version=1)
    scope_tasks.return_value = (selected, [selected, later])
    db = MagicMock()
    delete_task(db, access=access, task_id=selected.id, expected_version=1, local_date=date(2026, 9, 1), scope="THIS_AND_FUTURE")
    assert [call.args[0] for call in db.delete.call_args_list] == [selected, later]
    db.flush.assert_called_once()


@patch("app.services.v2_task._task")
def test_scope_locking_preserves_past_today_and_resolved(task_lookup) -> None:
    _, access = _context()
    batch_id = uuid.uuid4()
    selected = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=batch_id, lock_version=1)
    past = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 8, 31), generation_batch_id=batch_id, lock_version=1)
    today = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 1), generation_batch_id=batch_id, lock_version=1)
    resolved = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 4), generation_batch_id=batch_id, result=TaskResult.COMPLETED, resolved_at=datetime.now(timezone.utc), resolved_by_user_id=selected.responsible_user_id, lock_version=1)
    future = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=selected.master_task_id, responsible_user_id=selected.responsible_user_id, created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 5), generation_batch_id=batch_id, lock_version=1)
    task_lookup.return_value = selected
    db = MagicMock()
    db.scalars.return_value.all.return_value = [past, today, selected, resolved, future]
    locked_selected, affected = _mutation_scope_tasks(db, workspace_id=access.workspace.id, task_id=selected.id, scope="THIS_AND_FUTURE", local_date=date(2026, 9, 1))
    assert locked_selected is selected
    assert affected == [selected, future]
    statement = db.scalars.call_args.args[0]
    assert "FOR UPDATE" in str(statement)
    assert "ORDER BY tasks.planned_date, tasks.id" in str(statement)


@patch("app.services.v2_task._task")
def test_standalone_rejects_future_scope(task_lookup) -> None:
    _, access = _context()
    task_lookup.return_value = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), created_by_user_id=uuid.uuid4(), planned_date=date(2026, 9, 3), generation_batch_id=None, lock_version=1)
    with pytest.raises(TaskConflictError):
        _mutation_scope_tasks(MagicMock(), workspace_id=access.workspace.id, task_id=task_lookup.return_value.id, scope="THIS_AND_FUTURE", local_date=date(2026, 9, 1))


@patch("app.services.v2_task._task")
def test_future_programmed_task_cannot_be_resolved_early(task_lookup) -> None:
    actor, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=actor.id, created_by_user_id=actor.id, planned_date=date(2026, 9, 2), lock_version=1)
    task_lookup.return_value = task
    db = MagicMock()
    with pytest.raises(TaskConflictError):
        resolve_task(db, access=access, actor=actor, task_id=task.id, expected_version=1, result=TaskResult.COMPLETED, local_date=date(2026, 9, 1))
    db.flush.assert_not_called()


@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
def test_recurring_creation_uses_one_batch_and_deduplicated_dates(master, responsible) -> None:
    actor, access = _context()
    db = MagicMock()
    recurring = RecurringTaskCreate.model_validate({"master_task_id": str(uuid.uuid4()), "responsible_user_id": str(actor.id), "recurrence": {"pattern": "MONTHLY", "date_from": "2027-02-01", "date_until": "2027-02-28", "month_days": [29, 30, 31]}})
    # SQLAlchemy UUID defaults normally materialize on flush; emulate that boundary.
    def flush() -> None:
        batch = db.add.call_args.args[0]
        if getattr(batch, "id", None) is None:
            batch.id = uuid.uuid4()
    db.flush.side_effect = flush
    tasks = create_recurring_tasks(db, access=access, actor=actor, task_in=recurring)
    assert [task.planned_date for task in tasks] == [date(2027, 2, 28)]
    assert tasks[0].generation_batch_id == db.add.call_args.args[0].id
    db.add_all.assert_called_once_with(tasks)
    assert db.flush.call_count == 2
    db.commit.assert_not_called()


@patch("app.services.v2_task.recurrence_dates", return_value=[date(2026, 1, 1)] * (MAX_RECURRING_TASK_OCCURRENCES + 1))
@patch("app.services.v2_task._responsible")
@patch("app.services.v2_task._master")
def test_recurring_creation_enforces_occurrence_cap_before_writes(master, responsible, dates) -> None:
    actor, access = _context()
    value = RecurringTaskCreate.model_validate({"master_task_id": str(uuid.uuid4()), "recurrence": {"pattern": "DAILY", "date_from": "2026-01-01", "date_until": "2026-01-01"}})
    db = MagicMock()
    with pytest.raises(TaskRecurrenceError):
        create_recurring_tasks(db, access=access, actor=actor, task_in=value)
    db.add.assert_not_called()
    db.add_all.assert_not_called()
