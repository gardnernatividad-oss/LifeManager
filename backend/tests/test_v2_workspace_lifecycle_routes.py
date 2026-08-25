import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import (
    get_current_account,
    get_db,
    require_workspace_owner,
)
from app.main import app
from app.models.enums import WorkspaceKind, WorkspaceLifecycle
from app.services.v2_workspace_lifecycle import (
    WorkspaceLifecycleConflictError,
)


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _context():
    account = SimpleNamespace(id=uuid.uuid4(), account_status="ACTIVE")
    workspace = SimpleNamespace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=account.id, lifecycle=WorkspaceLifecycle.ACTIVE,
        deactivated_at=None, lock_version=1,
    )
    membership = SimpleNamespace(user_id=account.id, workspace_id=workspace.id)
    return account, SimpleNamespace(
        workspace=workspace, membership=membership, is_owner=True
    )


def _client(db, account, access):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_account] = lambda: account
    app.dependency_overrides[require_workspace_owner] = lambda: access
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_transfer_commits_once_and_rejects_mass_assignment() -> None:
    db = MagicMock()
    account, access = _context()
    target = uuid.uuid4()
    with patch(
        "app.api.v2.workspace_lifecycle.transfer_workspace_ownership",
        return_value=access.workspace,
    ) as service, patch(
        "app.api.v2.workspace_lifecycle.get_workspace_lifecycle",
        return_value=(access.workspace, False),
    ), _client(db, account, access) as client:
        response = client.post(
            f"/api/v2/workspaces/{access.workspace.id}/transfer-ownership",
            json={"target_user_id": str(target)},
        )
        hostile = client.post(
            f"/api/v2/workspaces/{access.workspace.id}/transfer-ownership",
            json={"target_user_id": str(target), "owner_user_id": str(target)},
        )
    assert response.status_code == 200
    assert service.call_args.kwargs["target_user_id"] == target
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(access.workspace)
    assert hostile.status_code == 422


def test_deactivate_commits_and_returns_server_derived_can_delete() -> None:
    db = MagicMock()
    account, access = _context()
    access.workspace.lifecycle = WorkspaceLifecycle.INACTIVE
    access.workspace.deactivated_at = NOW
    with patch(
        "app.api.v2.workspace_lifecycle.deactivate_shared_workspace",
        return_value=access.workspace,
    ), patch(
        "app.api.v2.workspace_lifecycle.get_workspace_lifecycle",
        return_value=(access.workspace, False),
    ), _client(db, account, access) as client:
        response = client.post(
            f"/api/v2/workspaces/{access.workspace.id}/deactivate"
        )
    assert response.status_code == 200
    assert response.json()["lifecycle"] == "INACTIVE"
    assert response.json()["can_delete"] is False
    db.commit.assert_called_once_with()


def test_hard_delete_returns_204_and_conflict_rolls_back() -> None:
    db = MagicMock()
    account, access = _context()
    with patch(
        "app.api.v2.workspace_lifecycle.resolve_owned_shared_workspace",
        return_value=access,
    ), patch(
        "app.api.v2.workspace_lifecycle.hard_delete_shared_workspace"
    ), _client(db, account, access) as client:
        response = client.delete(f"/api/v2/workspaces/{access.workspace.id}")
    assert response.status_code == 204 and response.content == b""
    db.commit.assert_called_once_with()

    db.reset_mock()
    with patch(
        "app.api.v2.workspace_lifecycle.resolve_owned_shared_workspace",
        return_value=access,
    ), patch(
        "app.api.v2.workspace_lifecycle.hard_delete_shared_workspace",
        side_effect=WorkspaceLifecycleConflictError("private"),
    ), _client(db, account, access) as client:
        conflict = client.delete(f"/api/v2/workspaces/{access.workspace.id}")
    assert conflict.status_code == 409
    assert "private" not in conflict.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_lifecycle_routes_require_authentication_and_are_explicit() -> None:
    app.dependency_overrides.clear()
    workspace_id = uuid.uuid4()
    with TestClient(app) as client:
        response = client.get(f"/api/v2/workspaces/{workspace_id}/lifecycle")
    assert response.status_code == 401

    paths = app.openapi()["paths"]
    assert "/api/v2/workspaces/{workspace_id}/lifecycle" in paths
    assert "/api/v2/workspaces/{workspace_id}/transfer-ownership" in paths
    assert "/api/v2/workspaces/{workspace_id}/deactivate" in paths
    assert "delete" in paths["/api/v2/workspaces/{workspace_id}"]
