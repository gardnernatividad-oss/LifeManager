import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import Category, MasterTask, Task, User, Workspace, WorkspaceKind
from app.services.task_service import (
    TaskMasterTaskNotFoundError,
    TaskNotFoundError,
    TaskOccurrenceConflictError,
    TaskPlanningConflictError,
    TaskVersionConflictError,
)


@pytest.fixture
def task_routes():
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client:
        yield client, db, user, workspace
    app.dependency_overrides.clear()


def _task(workspace_id: uuid.UUID, user_id: uuid.UUID, planned: date = date(2099, 8, 20)) -> Task:
    timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud",
        created_at=timestamp, updated_at=timestamp,
    )
    master = MasterTask(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Correr", normalized_name="correr",
        created_at=timestamp, updated_at=timestamp,
    )
    return Task(
        id=uuid.uuid4(), workspace_id=workspace_id, master_task_id=master.id,
        master_task=master, planned_date=planned, result=None, resolved_at=None,
        resolved_by_id=None, created_by_id=user_id, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )


def test_create_uses_authenticated_context_and_commits_once(task_routes) -> None:
    client, db, user, workspace = task_routes
    task = _task(workspace.id, user.id)
    with patch("app.api.v1.tasks.task_service.create_task", return_value=task) as service:
        response = client.post(
            "/api/v1/tasks",
            json={"master_task_id": str(task.master_task_id), "planned_date": str(task.planned_date)},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "PROGRAMADA"
    assert response.json()["master_task"]["category"]["name"] == "Salud"
    assert "title" not in response.json() and "workspace_id" not in response.json()
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["current_user"] is user
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(task)


def test_create_conflict_and_foreign_master_map_safely(task_routes) -> None:
    client, db, _user, _workspace = task_routes
    payload = {"master_task_id": str(uuid.uuid4()), "planned_date": "2026-08-20"}
    for error, expected in (
        (TaskOccurrenceConflictError("Task occurrence already exists"), 409),
        (TaskMasterTaskNotFoundError("Master task not found"), 404),
    ):
        db.reset_mock()
        with patch("app.api.v1.tasks.task_service.create_task", side_effect=error):
            response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == expected
        db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_bulk_create_commits_once_and_returns_independent_rows(task_routes) -> None:
    client, db, user, workspace = task_routes
    tasks = [_task(workspace.id, user.id, date(2099, 8, day)) for day in (20, 21)]
    with patch("app.api.v1.tasks.task_service.create_tasks_bulk", return_value=tasks):
        response = client.post(
            "/api/v1/tasks/bulk",
            json={
                "master_task_id": str(tasks[0].master_task_id),
                "start_date": "2099-08-20", "end_date": "2099-08-21", "pattern": "DAILY",
            },
        )
    assert response.status_code == 201
    assert response.json()["created_count"] == 2
    assert len(response.json()["items"]) == 2
    db.commit.assert_called_once_with(); assert db.refresh.call_count == 2


def test_bulk_conflict_rolls_back_without_commit(task_routes) -> None:
    client, db, _user, _workspace = task_routes
    with patch(
        "app.api.v1.tasks.task_service.create_tasks_bulk",
        side_effect=TaskOccurrenceConflictError("One or more Task occurrences already exist"),
    ):
        response = client.post(
            "/api/v1/tasks/bulk",
            json={"master_task_id": str(uuid.uuid4()), "start_date": "2026-08-20", "end_date": "2026-08-21", "pattern": "DAILY"},
        )
    assert response.status_code == 409
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_list_forwards_filters_has_metadata_and_is_read_only(task_routes) -> None:
    client, db, user, workspace = task_routes
    task = _task(workspace.id, user.id)
    with patch("app.api.v1.tasks.task_service.list_tasks", return_value=([task], 26)) as service:
        response = client.get(
            f"/api/v1/tasks?page=2&page_size=25&planned_from=2099-08-01&planned_to=2099-08-31"
            f"&master_task_id={task.master_task_id}&category_id={task.master_task.category_id}&status=PROGRAMADA"
        )
    assert response.status_code == 200
    assert response.json()["total_pages"] == 2 and response.json()["page"] == 2
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["status"].value == "PROGRAMADA"
    db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()


def test_update_preserves_date_only_contract_and_commits(task_routes) -> None:
    client, db, user, workspace = task_routes
    task = _task(workspace.id, user.id, date(2099, 8, 21)); task.lock_version = 2
    with patch("app.api.v1.tasks.task_service.update_task", return_value=task) as service:
        response = client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"planned_date": "2099-08-21", "lock_version": 1},
        )
    assert response.status_code == 200 and response.json()["lock_version"] == 2
    assert service.call_args.kwargs["task_in"].lock_version == 1
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(task)


@pytest.mark.parametrize(
    "error",
    [TaskPlanningConflictError("Only scheduled Tasks can be edited"), TaskVersionConflictError("Task version is stale")],
)
def test_update_conflicts_return_409_and_rollback(task_routes, error) -> None:
    client, db, _user, _workspace = task_routes
    with patch("app.api.v1.tasks.task_service.update_task", side_effect=error):
        response = client.patch(
            f"/api/v1/tasks/{uuid.uuid4()}",
            json={"planned_date": "2099-08-21", "lock_version": 1},
        )
    assert response.status_code == 409
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_single_delete_requires_version_and_commits(task_routes) -> None:
    client, db, _user, _workspace = task_routes
    task_id = uuid.uuid4()
    with patch("app.api.v1.tasks.task_service.delete_task") as service:
        response = client.delete(f"/api/v1/tasks/{task_id}?lock_version=3")
    assert response.status_code == 204 and response.content == b""
    assert service.call_args.kwargs["lock_version"] == 3
    db.commit.assert_called_once_with()
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 422


def test_bulk_delete_commits_once_and_returns_count(task_routes) -> None:
    client, db, _user, _workspace = task_routes
    payload = {"items": [{"id": str(uuid.uuid4()), "lock_version": 1}, {"id": str(uuid.uuid4()), "lock_version": 2}]}
    with patch("app.api.v1.tasks.task_service.delete_tasks_bulk", return_value=2):
        response = client.post("/api/v1/tasks/bulk-delete", json=payload)
    assert response.status_code == 200 and response.json() == {"deleted_count": 2}
    db.commit.assert_called_once_with()


def test_bulk_delete_failure_rolls_back_atomically(task_routes) -> None:
    client, db, _user, _workspace = task_routes
    with patch(
        "app.api.v1.tasks.task_service.delete_tasks_bulk",
        side_effect=TaskNotFoundError("One or more Tasks were not found"),
    ):
        response = client.post(
            "/api/v1/tasks/bulk-delete",
            json={"items": [{"id": str(uuid.uuid4()), "lock_version": 1}]},
        )
    assert response.status_code == 404
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_task_routes_require_authentication() -> None:
    db = MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/v1/tasks").status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["/api/v1/tasks?page=0", "/api/v1/tasks?page_size=101"])
def test_list_pagination_validation(path: str, task_routes) -> None:
    client, _db, _user, _workspace = task_routes
    assert client.get(path).status_code == 422
