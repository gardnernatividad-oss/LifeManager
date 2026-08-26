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
    return TaskRead(id=TASK_ID, workspace_id=WORKSPACE_ID, master_task_id=uuid.uuid4(), master_task_name="Comprar pan", category_id=uuid.uuid4(), category_name="Casa", responsible_user_id=USER_ID, responsible_display_name="Ana Uno", responsible_email="ana@example.com", planned_date=date(2026, 8, 26), state="PROGRAMADA", result=None, resolved_at=None, resolved_by_user_id=None, lock_version=1, can_edit=True, can_resolve=True, can_delete=True, created_at=now, updated_at=now)


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
    assert set(schema["properties"]) == {"master_task_id", "planned_date", "responsible_user_id"}
