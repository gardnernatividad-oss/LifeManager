import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import PendingItem, User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceKind
from app.schemas.v2_pending_item import PendingItemRead
from app.services.v2_pending_item import PendingItemConflictError
from app.services.v2_workspace import WorkspaceAccess


WORKSPACE_ID, ITEM_ID, USER_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def read() -> PendingItemRead:
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return PendingItemRead(id=ITEM_ID, workspace_id=WORKSPACE_ID, category_id=uuid.uuid4(), category_name="Casa", responsible_user_id=USER_ID, responsible_display_name="Ana Uno", responsible_email="ana@example.com", name="Compra", is_active=True, planned_date=date(2026, 9, 10), progress=0, state="NO_INICIADO", completion_date=None, compliance="EN_PLAZO", compliance_detail_days=9, lock_version=1, can_edit=True, can_update_progress=True, can_correct=False, can_deactivate=True, can_reactivate=False, can_delete=True, created_at=now, updated_at=now)


@pytest.fixture
def client():
    db = MagicMock()
    user = User(id=USER_ID, email="ana@example.com", hashed_password="hash", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=WORKSPACE_ID, name="Casa", kind=WorkspaceKind.SHARED, owner_user_id=USER_ID)
    access = WorkspaceAccess(workspace, WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    app.dependency_overrides[require_active_workspace_membership] = lambda: access
    try:
        yield TestClient(app), db, user, access
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v2.pending_items._read", return_value=read())
@patch("app.api.v2.pending_items.create_pending_item", return_value=PendingItem())
def test_create_uses_workspace_context_and_commits_once(create, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/pending-items", json={"category_id": str(uuid.uuid4()), "responsible_user_id": str(USER_ID), "name": "Compra", "planned_date": "2026-09-10"})
    assert response.status_code == 201 and response.json()["state"] == "NO_INICIADO"
    assert create.call_args.kwargs["actor"] is user and create.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.refresh.assert_called_once(); db.rollback.assert_not_called()


@patch("app.api.v2.pending_items._read", return_value=read())
@patch("app.api.v2.pending_items.update_pending_progress", return_value=PendingItem())
def test_progress_owns_transaction_and_uses_local_date(progress, projection, client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/pending-items/{ITEM_ID}/progress", json={"progress": 100, "lock_version": 1})
    assert response.status_code == 200
    assert progress.call_args.kwargs["progress"] == 100
    assert isinstance(progress.call_args.kwargs["local_date"], date)
    db.commit.assert_called_once()


@patch("app.api.v2.pending_items.update_pending_item", side_effect=PendingItemConflictError())
def test_conflict_rolls_back_safely(update, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/pending-items/{ITEM_ID}", json={"name": "Otro", "lock_version": 1})
    assert response.status_code == 409 and response.json()["error"]["code"] == "PENDING_ITEM_CONFLICT"
    db.rollback.assert_called_once(); db.commit.assert_not_called()


def test_mass_assignment_and_invalid_correction_are_rejected(client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/pending-items", json={"category_id": str(uuid.uuid4()), "name": "Compra", "planned_date": "2026-09-10", "workspace_id": str(WORKSPACE_ID), "completion_date": "2026-09-10"})
    assert response.status_code == 422
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/pending-items/{ITEM_ID}/correction", json={"progress": 100, "lock_version": 1})
    assert response.status_code == 422
    db.commit.assert_not_called()


def test_openapi_has_explicit_pending_surface_without_history_mutation() -> None:
    paths = {path: set(methods) for path, methods in app.openapi()["paths"].items() if path.startswith("/api/v2/workspaces/{workspace_id}/pending-items")}
    assert paths == {
        "/api/v2/workspaces/{workspace_id}/pending-items": {"get", "post"},
        "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}": {"get", "patch", "delete"},
        "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/progress": {"post"},
        "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/correction": {"post"},
        "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/deactivate": {"post"},
        "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/reactivate": {"post"},
    }
