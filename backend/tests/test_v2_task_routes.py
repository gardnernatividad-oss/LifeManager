import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import Task, User, Workspace, WorkspaceMember
from app.models.enums import TaskResult, WorkspaceKind
from app.schemas.v2_task import TaskRead
from app.services.v2_task import TaskConflictError, TaskPermissionError
from app.services.v2_workspace import WorkspaceAccess


WORKSPACE_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _read() -> TaskRead:
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    return TaskRead(id=TASK_ID, workspace_id=WORKSPACE_ID, master_task_id=uuid.uuid4(), master_task_name="Comprar pan", category_id=uuid.uuid4(), category_name="Casa", responsible_user_id=USER_ID, responsible_display_name="Ana Uno", responsible_email="ana@example.com", planned_date=date(2026, 8, 26), state="PROGRAMADA", result=None, resolved_at=None, resolved_by_user_id=None, lock_version=1, is_generated=False, can_edit_this=True, can_edit_future=False, can_delete_this=True, can_delete_future=False, can_edit=True, can_resolve=False, can_delete=True, created_at=now, updated_at=now)


@pytest.fixture
def client():
    db = MagicMock()
    user = User(id=USER_ID, email="ana@example.com", hashed_password="hash", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=WORKSPACE_ID, name="Casa", kind=WorkspaceKind.SHARED, owner_user_id=USER_ID)
    access = WorkspaceAccess(workspace=workspace, membership=WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    app.dependency_overrides[require_active_workspace_membership] = lambda: access
    try:
        yield TestClient(app), db, user, access
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v2.tasks._read", return_value=_read())
@patch("app.api.v2.tasks.create_task", return_value=Task())
def test_create_is_workspace_scoped_and_commits_once(create, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks", json={"master_task_id": str(uuid.uuid4()), "planned_date": "2026-08-26"})
    assert response.status_code == 201
    assert response.json()["state"] == "PROGRAMADA"
    assert create.call_args.kwargs["access"] is access
    assert create.call_args.kwargs["actor"] is user
    db.commit.assert_called_once()
    db.refresh.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.api.v2.tasks._read", return_value=_read())
@patch("app.api.v2.tasks.create_recurring_tasks", return_value=[Task(), Task()])
def test_recurring_create_commits_one_atomic_batch(recurring, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/recurring", json={"master_task_id": str(uuid.uuid4()), "responsible_user_id": str(USER_ID), "recurrence": {"pattern": "WEEKLY", "date_from": "2026-09-01", "date_until": "2026-09-30", "weekdays": [0, 2]}})
    assert response.status_code == 201
    assert response.json()["created_count"] == 2
    assert recurring.call_args.kwargs["access"] is access
    assert recurring.call_args.kwargs["actor"] is user
    db.commit.assert_called_once()
    assert db.refresh.call_count == 2


def test_recurring_create_rejects_internal_provenance_fields(client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/recurring", json={"master_task_id": str(uuid.uuid4()), "generation_batch_id": str(uuid.uuid4()), "entity_type": "TASK", "recurrence": {"pattern": "DAILY", "date_from": "2026-09-01", "date_until": "2026-09-02"}})
    assert response.status_code == 422
    db.commit.assert_not_called()


def test_create_rejects_mass_assignment(client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks", json={"master_task_id": str(uuid.uuid4()), "planned_date": "2026-08-26", "workspace_id": str(WORKSPACE_ID), "result": "COMPLETED"})
    assert response.status_code == 422
    db.commit.assert_not_called()


@patch("app.api.v2.tasks._read", return_value=_read())
@patch("app.api.v2.tasks.resolve_task", return_value=Task())
def test_complete_uses_current_account_and_commits(resolve, projection, client) -> None:
    http, db, user, _ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}/complete", json={"lock_version": 1})
    assert response.status_code == 200
    assert resolve.call_args.kwargs["actor"] is user
    assert resolve.call_args.kwargs["result"] == TaskResult.COMPLETED
    db.commit.assert_called_once()


@patch("app.api.v2.tasks.resolve_task", side_effect=TaskPermissionError())
def test_resolution_permission_is_403_and_rolls_back(resolve, client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}/not-complete", json={"lock_version": 1})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TASK_PERMISSION_DENIED"
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@patch("app.api.v2.tasks.update_task", side_effect=TaskConflictError())
def test_conflict_is_409_and_rolls_back(update, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}", json={"planned_date": "2026-08-27", "lock_version": 1})
    assert response.status_code == 409
    db.rollback.assert_called_once()


@patch("app.api.v2.tasks._read", return_value=_read())
@patch("app.api.v2.tasks.update_task", return_value=Task())
def test_future_scope_patch_is_explicit_and_commits_once(update, projection, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}", json={"responsible_user_id": str(USER_ID), "lock_version": 1, "scope": "THIS_AND_FUTURE"})
    assert response.status_code == 200
    assert update.call_args.kwargs["task_in"].scope == "THIS_AND_FUTURE"
    db.commit.assert_called_once()


@patch("app.api.v2.tasks.delete_task")
def test_future_scope_delete_is_explicit_and_commits_once(remove, client) -> None:
    http, db, *_ = client
    response = http.delete(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}?lock_version=1&scope=THIS_AND_FUTURE")
    assert response.status_code == 204
    assert remove.call_args.kwargs["scope"] == "THIS_AND_FUTURE"
    db.commit.assert_called_once()


def test_invalid_scope_is_rejected_without_writes(client) -> None:
    http, db, *_ = client
    response = http.delete(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}?lock_version=1&scope=FORGED")
    assert response.status_code == 422
    db.commit.assert_not_called()


@patch("app.api.v2.tasks.list_tasks", return_value=([], 0))
@patch("app.api.v2.tasks.local_today", return_value=date(2026, 8, 25))
def test_list_forwards_derived_state_and_generated_filters(today, listing, client) -> None:
    http, db, *_ = client
    response = http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks?state=PENDIENTE&generated=true&page=1&page_size=25")
    assert response.status_code == 200
    assert listing.call_args.kwargs["state"] == "PENDIENTE"
    assert listing.call_args.kwargs["generated"] is True
    assert listing.call_args.kwargs["local_date"] == date(2026, 8, 25)
    db.commit.assert_not_called()


@patch("app.api.v2.tasks._read", return_value=_read())
@patch("app.api.v2.tasks.update_task", return_value=Task())
@patch("app.api.v2.tasks.local_today", return_value=date(2026, 8, 25))
def test_patch_supplies_authoritative_user_local_date(local_date, update, projection, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/tasks/{TASK_ID}", json={"planned_date": "2026-08-27", "lock_version": 1})
    assert response.status_code == 200
    assert update.call_args.kwargs["local_date"] == date(2026, 8, 25)
    db.commit.assert_called_once()


def test_openapi_exposes_explicit_task_contracts() -> None:
    document = app.openapi()
    path = document["paths"]["/api/v2/workspaces/{workspace_id}/tasks"]
    assert set(path) == {"get", "post"}
    schema = document["components"]["schemas"]["TaskCreate"]
    assert set(schema["properties"]) == {"master_task_id", "custom_name", "custom_category_id", "planned_date", "responsible_user_id"}
    recurring = document["components"]["schemas"]["RecurringTaskCreate"]
    assert set(recurring["properties"]) == {"master_task_id", "custom_name", "custom_category_id", "responsible_user_id", "recurrence"}
    update = document["components"]["schemas"]["TaskUpdate"]
    assert set(update["properties"]) == {"master_task_id", "custom_name", "custom_category_id", "planned_date", "responsible_user_id", "lock_version", "scope"}
    task_paths = {
        route: set(operations)
        for route, operations in document["paths"].items()
        if route.startswith("/api/v2/workspaces/{workspace_id}/tasks")
    }
    assert task_paths == {
        "/api/v2/workspaces/{workspace_id}/tasks": {"get", "post"},
        "/api/v2/workspaces/{workspace_id}/tasks/recurring": {"post"},
        "/api/v2/workspaces/{workspace_id}/tasks/{task_id}": {"get", "patch", "delete"},
        "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/complete": {"post"},
        "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/not-complete": {"post"},
        "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/correct-result": {"post"},
    }
    read = document["components"]["schemas"]["TaskRead"]["properties"]
    assert "generation_batch_id" not in read
    assert "created_by_user_id" not in read
    assert "entity_type" not in read
