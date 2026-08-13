import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import Category, MasterTask, Task, TaskResult, User, Workspace, WorkspaceKind
from app.services.task_service import TaskNotFoundError, TaskResultConflictError, TaskVersionConflictError


@pytest.fixture
def tracking_routes():
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client:
        yield client, db, user, workspace
    app.dependency_overrides.clear()


def _resolved_task(workspace_id: uuid.UUID, user_id: uuid.UUID) -> Task:
    timestamp = datetime.now(timezone.utc)
    category = Category(id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud")
    master = MasterTask(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Correr", normalized_name="correr",
    )
    return Task(
        id=uuid.uuid4(), workspace_id=workspace_id, master_task_id=master.id,
        master_task=master, planned_date=date(2026, 8, 12),
        result=TaskResult.COMPLETED, resolved_at=timestamp, resolved_by_id=user_id,
        lock_version=2, created_at=timestamp, updated_at=timestamp,
    )


def test_result_entry_commits_once_and_serializes_tracking_fields(tracking_routes) -> None:
    client, db, user, workspace = tracking_routes
    task = _resolved_task(workspace.id, user.id)
    with patch("app.api.v1.tasks.task_service.set_task_result", return_value=task) as service:
        response = client.patch(
            f"/api/v1/tasks/{task.id}/result",
            json={"result": "COMPLETED", "lock_version": 1},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "COMPLETED"
    assert payload["resolved_at"] is not None
    assert payload["resolved_by_id"] == str(user.id)
    assert payload["status"] == "COMPLETADA"
    assert payload["lock_version"] == 2
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["current_user"] is user
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(task)
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (TaskResultConflictError("Scheduled Tasks cannot receive a result"), 409),
        (TaskVersionConflictError("Task version is stale"), 409),
        (TaskNotFoundError("Task not found"), 404),
    ],
)
def test_result_domain_failures_roll_back(tracking_routes, error, status_code) -> None:
    client, db, _user, _workspace = tracking_routes
    with patch("app.api.v1.tasks.task_service.set_task_result", side_effect=error):
        response = client.patch(
            f"/api/v1/tasks/{uuid.uuid4()}/result",
            json={"result": "NOT_COMPLETED", "lock_version": 1},
        )
    assert response.status_code == status_code
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "CANCELLED", "lock_version": 1},
        {"result": None, "lock_version": 1},
        {"result": "COMPLETED"},
        {"result": "COMPLETED", "lock_version": 1, "planned_date": "2026-08-13"},
        {"result": "COMPLETED", "lock_version": 1, "workspace_id": str(uuid.uuid4())},
    ],
)
def test_result_schema_rejects_invalid_or_cross_boundary_fields(tracking_routes, payload) -> None:
    client, db, _user, _workspace = tracking_routes
    response = client.patch(f"/api/v1/tasks/{uuid.uuid4()}/result", json=payload)
    assert response.status_code == 422
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_tracking_list_exposes_result_and_resolution_timestamp(tracking_routes) -> None:
    client, db, user, workspace = tracking_routes
    task = _resolved_task(workspace.id, user.id)
    with patch("app.api.v1.tasks.task_service.list_tasks", return_value=([task], 1)):
        response = client.get("/api/v1/tasks?status=COMPLETADA&page=1&page_size=25")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["result"] == "COMPLETED"
    assert item["resolved_at"] is not None
    assert item["master_task"]["name"] == "Correr"
    assert item["master_task"]["category"]["name"] == "Salud"
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_result_endpoint_requires_authentication() -> None:
    app.dependency_overrides[get_db] = lambda: MagicMock(spec=Session)
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/tasks/{uuid.uuid4()}/result",
            json={"result": "COMPLETED", "lock_version": 1},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 401
