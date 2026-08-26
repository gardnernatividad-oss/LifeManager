import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import Category, MasterTask, Task, User, Workspace, WorkspaceMember
from app.models.enums import TaskResult, WorkspaceKind
from app.schemas.v2_task import TaskCreate, TaskUpdate
from app.services.v2_task import TaskConflictError, TaskPermissionError, create_task, delete_task, resolve_task, task_projection, update_task
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
    _, state, can_edit, can_resolve, can_delete = task_projection(db, task=task, actor_id=actor.id, local_date=date(2026, 9, 1))
    assert (state, can_edit, can_resolve, can_delete) == ("PROGRAMADA", True, False, True)
    task.planned_date = date(2026, 9, 1)
    _, state, can_edit, can_resolve, can_delete = task_projection(db, task=task, actor_id=actor.id, local_date=date(2026, 9, 1))
    assert (state, can_edit, can_resolve, can_delete) == ("PENDIENTE", False, True, False)


@patch("app.services.v2_task._task")
def test_future_programmed_task_cannot_be_resolved_early(task_lookup) -> None:
    actor, access = _context()
    task = Task(id=uuid.uuid4(), workspace_id=access.workspace.id, master_task_id=uuid.uuid4(), responsible_user_id=actor.id, created_by_user_id=actor.id, planned_date=date(2026, 9, 2), lock_version=1)
    task_lookup.return_value = task
    db = MagicMock()
    with pytest.raises(TaskConflictError):
        resolve_task(db, access=access, actor=actor, task_id=task.id, expected_version=1, result=TaskResult.COMPLETED, local_date=date(2026, 9, 1))
    db.flush.assert_not_called()
