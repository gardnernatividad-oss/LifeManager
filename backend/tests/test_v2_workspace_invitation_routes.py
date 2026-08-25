import uuid

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_workspace_owner
from app.main import app
from app.models.enums import InvitationStatus, WorkspaceKind
from app.services.v2_workspace_invitation import WorkspaceInvitationConflictError


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _account():
    return SimpleNamespace(id=uuid.uuid4(), account_status="ACTIVE")


def _invitation(account, workspace_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), workspace_id=workspace_id or uuid.uuid4(),
        recipient_email="member@example.com", recipient_user_id=account.id,
        status=InvitationStatus.PENDING, expires_at=NOW + timedelta(days=14),
        created_at=NOW,
    )


def _client(db, account, owner_access=None):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_account] = lambda: account
    if owner_access is not None:
        app.dependency_overrides[require_workspace_owner] = lambda: owner_access
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_create_route_has_strict_body_and_commits_once() -> None:
    db = MagicMock()
    account = _account()
    workspace = SimpleNamespace(id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED)
    access = SimpleNamespace(workspace=workspace, membership=SimpleNamespace(user_id=account.id))
    invitation = _invitation(account, workspace.id)
    with patch("app.api.v2.workspace_invitations.create_workspace_invitation", return_value=invitation) as service, _client(db, account, access) as client:
        response = client.post(
            f"/api/v2/workspaces/{workspace.id}/invitations",
            json={"email": "MEMBER@example.com"},
        )
    assert response.status_code == 201
    assert response.json()["recipient_email"] == "member@example.com"
    assert service.call_args.kwargs["owner_access"] is access
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(invitation)
    db.rollback.assert_not_called()

    with _client(db, account, access) as client:
        rejected = client.post(
            f"/api/v2/workspaces/{workspace.id}/invitations",
            json={"email": "member@example.com", "status": "ACCEPTED"},
        )
    assert rejected.status_code == 422


def test_accept_conflict_rolls_back_and_returns_safe_409() -> None:
    db = MagicMock()
    account = _account()
    with patch(
        "app.api.v2.workspace_invitations.accept_workspace_invitation",
        side_effect=WorkspaceInvitationConflictError("private"),
    ), _client(db, account) as client:
        response = client.post(
            f"/api/v2/workspace-invitations/{uuid.uuid4()}/accept"
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVITATION_CONFLICT"
    assert "private" not in response.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_anonymous_invitation_listing_is_rejected() -> None:
    db = MagicMock()
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get("/api/v2/workspace-invitations")
    assert response.status_code == 401
    db.commit.assert_not_called()


def test_openapi_invitation_contract_exposes_no_token_or_privileged_fields() -> None:
    openapi = app.openapi()
    paths = openapi["paths"]
    expected = {
        "/api/v2/workspaces/{workspace_id}/invitations",
        "/api/v2/workspace-invitations",
        "/api/v2/workspace-invitations/{invitation_id}/accept",
        "/api/v2/workspace-invitations/{invitation_id}/reject",
        "/api/v2/workspace-invitations/{invitation_id}/cancel",
    }
    assert expected <= set(paths)
    serialized = str({path: paths[path] for path in expected})
    for forbidden in ("token_digest", "raw_token", "global_role", "owner_user_id"):
        assert forbidden not in serialized
