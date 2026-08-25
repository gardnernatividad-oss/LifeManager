import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import (
    get_current_account,
    get_db,
    require_active_workspace_membership,
    require_workspace_owner,
)
from app.main import app
from app.models.enums import MembershipStatus, WorkspaceKind
from app.services.v2_workspace_member import (
    WorkspaceMemberConflictError,
    WorkspaceMemberNotFoundError,
)


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _context(*, owner: bool = False):
    account = SimpleNamespace(
        id=uuid.uuid4(),
        email="member@example.com",
        first_name="Ana",
        last_name="Pérez",
        account_status="ACTIVE",
    )
    workspace = SimpleNamespace(
        id=uuid.uuid4(),
        name="Familia",
        kind=WorkspaceKind.SHARED,
        owner_user_id=account.id if owner else uuid.uuid4(),
    )
    membership = SimpleNamespace(
        user_id=account.id,
        workspace_id=workspace.id,
        status=MembershipStatus.ACTIVE,
        joined_at=NOW,
        ended_at=None,
    )
    return account, SimpleNamespace(
        workspace=workspace,
        membership=membership,
        is_owner=owner,
    )


def _client(db, account=None, access=None, owner_access=None):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if account is not None:
        app.dependency_overrides[get_current_account] = lambda: account
    if access is not None:
        app.dependency_overrides[require_active_workspace_membership] = lambda: access
    if owner_access is not None:
        app.dependency_overrides[require_workspace_owner] = lambda: owner_access
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_active_member_lists_minimal_member_dtos_without_writes() -> None:
    db = MagicMock()
    account, access = _context()
    member = access.membership
    with patch(
        "app.api.v2.workspace_members.list_workspace_members",
        return_value=[(member, account)],
    ) as service, _client(db, account, access) as client:
        response = client.get(
            f"/api/v2/workspaces/{access.workspace.id}/members"
        )

    assert response.status_code == 200
    assert response.json() == [{
        "user_id": str(account.id),
        "display_name": "Ana Pérez",
        "email": account.email,
        "role": "Miembro",
        "status": "ACTIVE",
        "joined_at": NOW.isoformat().replace("+00:00", "Z"),
        "ended_at": None,
    }]
    assert service.call_args.kwargs["access"] is access
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.flush.assert_not_called()


def test_owner_removal_commits_once_and_returns_removed_member() -> None:
    db = MagicMock()
    owner, access = _context(owner=True)
    target, _ = _context()
    member = SimpleNamespace(
        user_id=target.id,
        workspace_id=access.workspace.id,
        status=MembershipStatus.REMOVED,
        joined_at=NOW,
        ended_at=NOW,
    )
    with patch(
        "app.api.v2.workspace_members.remove_workspace_member",
        return_value=(member, target),
    ) as service, _client(db, owner, access, access) as client:
        response = client.delete(
            f"/api/v2/workspaces/{access.workspace.id}/members/{target.id}"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "REMOVED"
    assert response.json()["role"] == "Miembro"
    assert service.call_args.kwargs["target_user_id"] == target.id
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(member)
    db.rollback.assert_not_called()


def test_member_leave_commits_once_and_returns_left_membership() -> None:
    db = MagicMock()
    account, access = _context()
    access.membership.status = MembershipStatus.LEFT
    access.membership.ended_at = NOW
    with patch(
        "app.api.v2.workspace_members.leave_shared_workspace",
        return_value=access.membership,
    ) as service, _client(db, account, access) as client:
        response = client.post(
            f"/api/v2/workspaces/{access.workspace.id}/leave"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "LEFT"
    assert service.call_args.kwargs["account"] is account
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(access.membership)


def test_known_lifecycle_errors_rollback_with_safe_contract() -> None:
    db = MagicMock()
    owner, access = _context(owner=True)
    with patch(
        "app.api.v2.workspace_members.remove_workspace_member",
        side_effect=WorkspaceMemberNotFoundError("private target"),
    ), _client(db, owner, access, access) as client:
        missing = client.delete(
            f"/api/v2/workspaces/{access.workspace.id}/members/{uuid.uuid4()}"
        )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "WORKSPACE_MEMBER_NOT_FOUND"
    assert "private target" not in missing.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()

    db.reset_mock()
    with patch(
        "app.api.v2.workspace_members.leave_shared_workspace",
        side_effect=WorkspaceMemberConflictError("owner"),
    ), _client(db, owner, access) as client:
        conflict = client.post(
            f"/api/v2/workspaces/{access.workspace.id}/leave"
        )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "WORKSPACE_MEMBERSHIP_CONFLICT"
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_anonymous_and_nonmember_access_remain_masked() -> None:
    db = MagicMock()
    workspace_id = uuid.uuid4()
    with _client(db) as client:
        anonymous = client.get(f"/api/v2/workspaces/{workspace_id}/members")
    assert anonymous.status_code == 401

    account, _ = _context()
    with _client(db, account) as client:
        db.execute.return_value.one_or_none.return_value = None
        foreign = client.get(f"/api/v2/workspaces/{workspace_id}/members")
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


def test_ordinary_member_and_global_admin_have_no_remove_bypass() -> None:
    for global_role in (None, "GLOBAL_ADMIN"):
        db = MagicMock()
        account, access = _context()
        account.global_role = global_role
        with _client(db, account, access) as client:
            response = client.delete(
                f"/api/v2/workspaces/{access.workspace.id}/members/{uuid.uuid4()}"
            )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WORKSPACE_OWNER_REQUIRED"
        db.commit.assert_not_called()


def test_openapi_membership_contract_is_explicit_and_has_no_mass_assignment() -> None:
    openapi = app.openapi()
    paths = openapi["paths"]
    expected = {
        "/api/v2/workspaces/{workspace_id}/members",
        "/api/v2/workspaces/{workspace_id}/members/{user_id}",
        "/api/v2/workspaces/{workspace_id}/leave",
    }
    assert expected <= set(paths)
    assert set(paths["/api/v2/workspaces/{workspace_id}/members"]) == {
        "get"
    }
    assert set(paths["/api/v2/workspaces/{workspace_id}/members/{user_id}"]) == {
        "delete"
    }
    assert set(paths["/api/v2/workspaces/{workspace_id}/leave"]) == {"post"}
    serialized = str({path: paths[path] for path in expected})
    for forbidden in (
        "owner_user_id", "global_role", "lock_version", "calendar_visibility",
        "hashed_password", "joined_at=", "ended_at=",
    ):
        assert forbidden not in serialized
