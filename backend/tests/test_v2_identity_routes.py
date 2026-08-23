import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db
from app.main import app
from app.models.enums import AccountStatus, GlobalRole
from app.services.v2_identity import (
    AccountStateConflictError,
    AdminAccountNotFoundError,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _account(
    *,
    status: AccountStatus = AccountStatus.ACTIVE,
    global_role: GlobalRole | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="person@example.com",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        global_role=global_role,
        email_verified_at=(
            None
            if status is AccountStatus.PENDING_EMAIL_VERIFICATION
            else NOW
        ),
        status_changed_at=NOW,
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _client(
    db: MagicMock,
    *,
    account: SimpleNamespace | None = None,
    raise_server_exceptions: bool = True,
) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if account is not None:
        app.dependency_overrides[get_current_account] = lambda: account
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_registration_returns_neutral_acknowledgement_and_owns_transaction() -> None:
    db = MagicMock()
    pending = _account(status=AccountStatus.PENDING_EMAIL_VERIFICATION)
    payload = {
        "email": "person@example.com",
        "password": "plain password",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    with patch(
        "app.api.v2.identity.create_registration_request",
        return_value=pending,
    ) as service, _client(db) as client:
        response = client.post("/api/v2/auth/registration-requests", json=payload)

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert "password" not in response.text
    assert "PENDING" not in response.text
    assert service.call_args.kwargs["registration_in"].password == "plain password"
    db.commit.assert_called_once_with()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_duplicate_registration_returns_same_neutral_acknowledgement() -> None:
    db = MagicMock()
    payload = {
        "email": "person@example.com",
        "password": "plain password",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    from app.services.v2_identity import RegistrationRequestConflictError

    with patch(
        "app.api.v2.identity.create_registration_request",
        side_effect=RegistrationRequestConflictError("duplicate"),
    ), _client(db) as client:
        response = client.post("/api/v2/auth/registration-requests", json=payload)

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_registration_rejects_mass_assignment_before_service() -> None:
    db = MagicMock()
    payload = {
        "email": "person@example.com",
        "password": "plain password",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "global_role": "GLOBAL_ADMIN",
        "account_status": "ACTIVE",
        "owner_user_id": str(uuid.uuid4()),
        "is_verified": True,
    }
    with patch("app.api.v2.identity.create_registration_request") as service, _client(db) as client:
        response = client.post("/api/v2/auth/registration-requests", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    service.assert_not_called()
    db.commit.assert_not_called()


def test_approval_requires_authentication_and_global_admin() -> None:
    db = MagicMock()
    target_id = uuid.uuid4()
    with _client(db) as client:
        unauthenticated = client.post(
            f"/api/v2/admin/account-requests/{target_id}/approve"
        )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "INVALID_SESSION"

    ordinary = _account()
    with _client(db, account=ordinary) as client:
        forbidden = client.post(
            f"/api/v2/admin/account-requests/{target_id}/approve"
        )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "GLOBAL_ADMIN_REQUIRED"
    db.commit.assert_not_called()


def test_disabled_persisted_global_admin_is_denied() -> None:
    db = MagicMock()
    disabled_admin = _account(
        status=AccountStatus.DISABLED,
        global_role=GlobalRole.GLOBAL_ADMIN,
    )
    with _client(db, account=disabled_admin) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION"
    db.commit.assert_not_called()


def test_global_admin_approval_commits_once_and_returns_minimized_response() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    target = _account()
    target.account_status = AccountStatus.ACTIVE
    with patch(
        "app.api.v2.identity.approve_registration_request",
        return_value=target,
    ) as service, _client(db, account=admin) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{target.id}/approve"
        )

    assert response.status_code == 200
    assert response.json()["account_status"] == "ACTIVE"
    assert set(response.json()) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "timezone",
        "account_status",
        "email_verified_at",
        "created_at",
    }
    assert service.call_args.kwargs == {
        "user_id": target.id,
        "actor": admin,
    }
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(target)
    db.rollback.assert_not_called()


def test_global_admin_lists_pending_requests_without_writes() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    first = _account(status=AccountStatus.PENDING_APPROVAL)
    second = _account(status=AccountStatus.PENDING_APPROVAL)
    with patch(
        "app.api.v2.identity.list_pending_registration_requests",
        return_value=[first, second],
    ), _client(db, account=admin) as client:
        response = client.get("/api/v2/admin/account-requests")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [item["id"] for item in response.json()["items"]] == [
        str(first.id),
        str(second.id),
    ]
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.flush.assert_not_called()


def test_approval_conflict_rolls_back_without_commit() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    target_id = uuid.uuid4()
    with patch(
        "app.api.v2.identity.approve_registration_request",
        side_effect=AccountStateConflictError("invalid state"),
    ), _client(db, account=admin) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{target_id}/approve"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACCOUNT_STATE_CONFLICT"
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_malformed_admin_user_id_uses_safe_validation_envelope() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    with _client(db, account=admin) as client:
        response = client.post(
            "/api/v2/admin/account-requests/not-a-uuid/approve"
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "not-a-uuid" not in response.text
    db.commit.assert_not_called()


def test_missing_pending_account_uses_safe_not_found_envelope() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    with patch(
        "app.api.v2.identity.get_admin_account",
        side_effect=AdminAccountNotFoundError("private detail"),
    ), _client(db, account=admin) as client:
        response = client.get(
            f"/api/v2/admin/account-requests/{uuid.uuid4()}"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert "private detail" not in response.text
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_unexpected_approval_failure_rolls_back_atomically() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    with patch(
        "app.api.v2.identity.approve_registration_request",
        side_effect=RuntimeError("provisioning failed"),
    ), _client(db, account=admin, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve"
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "provisioning" not in response.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_rejection_commits_and_does_not_expose_sensitive_fields() -> None:
    db = MagicMock()
    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    rejected = _account(status=AccountStatus.REJECTED)
    with patch(
        "app.api.v2.identity.reject_registration_request",
        return_value=rejected,
    ) as service, _client(db, account=admin) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{rejected.id}/reject",
            json={"reason": "Not approved"},
        )

    assert response.status_code == 200
    assert response.json()["account_status"] == "REJECTED"
    assert "hashed_password" not in response.json()
    assert service.call_args.kwargs["actor"] is admin
    assert service.call_args.kwargs["reason"] == "Not approved"
    db.commit.assert_called_once_with()


def test_rejection_requires_global_admin_and_conflict_rolls_back() -> None:
    db = MagicMock()
    target_id = uuid.uuid4()
    with _client(db, account=_account()) as client:
        forbidden = client.post(
            f"/api/v2/admin/account-requests/{target_id}/reject",
            json={},
        )
    assert forbidden.status_code == 403

    admin = _account(global_role=GlobalRole.GLOBAL_ADMIN)
    with patch(
        "app.api.v2.identity.reject_registration_request",
        side_effect=AccountStateConflictError("already handled"),
    ), _client(db, account=admin) as client:
        conflict = client.post(
            f"/api/v2/admin/account-requests/{target_id}/reject",
            json={},
        )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ACCOUNT_STATE_CONFLICT"
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_openapi_contains_only_explicit_v2_identity_fields() -> None:
    openapi = app.openapi()
    assert {
        "/api/v2/auth/registration-requests",
        "/api/v2/admin/account-requests",
        "/api/v2/admin/account-requests/{user_id}",
        "/api/v2/admin/account-requests/{user_id}/approve",
        "/api/v2/admin/account-requests/{user_id}/reject",
    } <= set(openapi["paths"])
    schemas = openapi["components"]["schemas"]
    registration_fields = set(schemas["RegistrationRequestCreate"]["properties"])
    assert registration_fields == {
        "email",
        "password",
        "first_name",
        "last_name",
        "timezone",
    }
    serialized = str(schemas)
    assert "hashed_password" not in serialized
    assert "token_digest" not in serialized
    assert not any("account-state-events" in path for path in openapi["paths"])
    assert set(schemas["RegistrationRequestAcknowledgement"]["properties"]) == {
        "accepted"
    }
    assert set(schemas["AdminAccountSummary"]["properties"]) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "timezone",
        "account_status",
        "email_verified_at",
        "created_at",
    }
    assert "RegistrationRequestRead" not in schemas
