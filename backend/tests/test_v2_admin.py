import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db
from app.main import app
from app.models import User, UserAccountStateEvent
from app.models.enums import AccountStatus, GlobalRole
from app.services.v2_admin import AdminUserPage, change_admin_account_state
from app.services.v2_identity import AccountStateConflictError


NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)


def _account(*, status=AccountStatus.ACTIVE, role=None, lock_version=1):
    return SimpleNamespace(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.com", first_name="Ada",
        last_name="Lovelace", timezone="America/Lima", account_status=status,
        global_role=role, email_verified_at=NOW, status_changed_at=NOW,
        lock_version=lock_version, created_at=NOW, updated_at=NOW,
    )


def _client(db: MagicMock, account=None) -> TestClient:
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    if account is not None:
        app.dependency_overrides[get_current_account] = lambda: account
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _rate_limit():
    with patch("app.api.v2.admin.enforce_rate_limit"):
        yield


def test_admin_user_list_is_paginated_minimal_and_read_only() -> None:
    db = MagicMock()
    admin = _account(role=GlobalRole.GLOBAL_ADMIN)
    user = _account()
    result = AdminUserPage([user], 1, 1, 25, 1)
    with patch("app.api.v2.admin.list_admin_users", return_value=result) as service, _client(db, admin) as client:
        response = client.get("/api/v2/admin/users?page=1&page_size=25&account_status=ACTIVE&search=ada")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert set(item) == {"id", "email", "first_name", "last_name", "timezone", "account_status", "global_role", "email_verified_at", "status_changed_at", "lock_version", "created_at"}
    assert "hashed_password" not in response.text and "token" not in response.text
    assert service.call_args.kwargs["account_status"] == AccountStatus.ACTIVE
    db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()


def test_admin_routes_require_active_global_admin() -> None:
    db = MagicMock()
    with _client(db, _account()) as client:
        assert client.get("/api/v2/admin/users").status_code == 403
    with _client(db, _account(status=AccountStatus.DISABLED, role=GlobalRole.GLOBAL_ADMIN)) as client:
        assert client.get("/api/v2/admin/users").status_code == 401
    db.commit.assert_not_called()


def test_disable_commits_once_and_rejects_mass_assignment() -> None:
    db = MagicMock()
    admin = _account(role=GlobalRole.GLOBAL_ADMIN)
    target = _account(status=AccountStatus.DISABLED, lock_version=2)
    with patch("app.api.v2.admin.change_admin_account_state", return_value=target) as service, _client(db, admin) as client:
        response = client.post(f"/api/v2/admin/users/{target.id}/disable", json={"lock_version": 1})
        hostile = client.post(f"/api/v2/admin/users/{target.id}/disable", json={"lock_version": 1, "global_role": "GLOBAL_ADMIN"})
    assert response.status_code == 200
    assert service.call_args.kwargs["new_status"] == AccountStatus.DISABLED
    assert db.commit.call_count == 1
    assert hostile.status_code == 422


def test_state_conflict_rolls_back_and_hides_detail() -> None:
    db = MagicMock()
    admin = _account(role=GlobalRole.GLOBAL_ADMIN)
    with patch("app.api.v2.admin.change_admin_account_state", side_effect=AccountStateConflictError("private")), _client(db, admin) as client:
        response = client.post(f"/api/v2/admin/users/{uuid.uuid4()}/reactivate", json={"lock_version": 1})
    assert response.status_code == 409
    assert "private" not in response.text
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_service_locks_audits_and_flushes_without_transaction_ownership() -> None:
    db = MagicMock()
    admin = User(id=uuid.uuid4(), account_status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    target = User(id=uuid.uuid4(), account_status=AccountStatus.ACTIVE, global_role=None, email_verified_at=NOW, status_changed_at=NOW, lock_version=1)
    db.scalar.return_value = target
    changed = change_admin_account_state(db, user_id=target.id, expected_lock_version=1, new_status=AccountStatus.DISABLED, actor=admin, reason="Security")
    assert changed.account_status == AccountStatus.DISABLED and changed.lock_version == 2
    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is not None
    assert any(isinstance(call.args[0], UserAccountStateEvent) for call in db.add.call_args_list)
    db.flush.assert_called_once_with(); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_service_rejects_stale_and_global_admin_targets_before_flush() -> None:
    db = MagicMock()
    actor = User(id=uuid.uuid4())
    stale = User(id=uuid.uuid4(), account_status=AccountStatus.ACTIVE, lock_version=2)
    db.scalar.return_value = stale
    with pytest.raises(AccountStateConflictError):
        change_admin_account_state(db, user_id=stale.id, expected_lock_version=1, new_status=AccountStatus.DISABLED, actor=actor, reason=None)
    protected = User(id=uuid.uuid4(), account_status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN, lock_version=1)
    db.scalar.return_value = protected
    with pytest.raises(AccountStateConflictError):
        change_admin_account_state(db, user_id=protected.id, expected_lock_version=1, new_status=AccountStatus.DISABLED, actor=actor, reason=None)
    db.flush.assert_not_called()


def test_openapi_contains_admin_users_without_secret_fields() -> None:
    schema = app.openapi()
    assert {"/api/v2/admin/users", "/api/v2/admin/users/{user_id}", "/api/v2/admin/users/{user_id}/disable", "/api/v2/admin/users/{user_id}/reactivate"} <= set(schema["paths"])
    serialized = str(schema["components"]["schemas"]["AdminUserSummary"])
    assert "hashed_password" not in serialized and "token_digest" not in serialized
