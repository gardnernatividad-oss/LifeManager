import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_db
from app.main import app
from app.services.password_recovery_service import (
    InvalidPasswordResetTokenError,
    IssuedPasswordReset,
    PasswordRecoveryIssuanceConflictError,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
RAW_TOKEN = "R" * 43


def _client(db: MagicMock, *, raise_server_exceptions: bool = True) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_recovery_response_is_identical_for_eligible_and_unknown_email() -> None:
    issued = IssuedPasswordReset(
        recipient="person@example.com",
        raw_token=RAW_TOKEN,
        expires_at=NOW,
    )
    responses = []
    for service_result, deliveries in ((issued, 1), (None, 0)):
        db = MagicMock()
        with patch(
            "app.api.v2.identity.request_password_recovery",
            return_value=service_result,
        ) as service, patch(
            "app.api.v2.identity.email_delivery.send_password_reset_email"
        ) as delivery, _client(db) as client:
            response = client.post(
                "/api/v2/auth/password-recovery-requests",
                json={"email": " Person@Example.com "},
            )
        responses.append((response.status_code, response.json()))
        assert service.call_args.kwargs["email"] == "person@example.com"
        assert delivery.call_count == deliveries
        db.commit.assert_called_once_with()
        db.rollback.assert_not_called()
    assert responses == [(202, {"accepted": True}), (202, {"accepted": True})]


def test_concurrent_issuance_conflict_is_also_neutral() -> None:
    db = MagicMock()
    with patch(
        "app.api.v2.identity.request_password_recovery",
        side_effect=PasswordRecoveryIssuanceConflictError("private constraint"),
    ), _client(db) as client:
        response = client.post(
            "/api/v2/auth/password-recovery-requests",
            json={"email": "person@example.com"},
        )
    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert "constraint" not in response.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_valid_reset_commits_once_and_returns_minimal_response() -> None:
    db = MagicMock()
    with patch("app.api.v2.identity.reset_password") as service, _client(db) as client:
        response = client.post(
            "/api/v2/auth/password-resets",
            json={"token": RAW_TOKEN, "new_password": "NewPassword!"},
        )
    assert response.status_code == 200
    assert response.json() == {"password_reset": True}
    service.assert_called_once_with(
        db,
        raw_token=RAW_TOKEN,
        new_password="NewPassword!",
    )
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


def test_registration_and_reset_share_password_policy_and_redact_input() -> None:
    invalid_passwords = (
        "Short1!",
        "lowercase!",
        "UPPERCASE!",
        "NoSymbols1",
        "A" * 129 + "a!",
    )
    for password in invalid_passwords:
        db = MagicMock()
        with patch(
            "app.api.v2.identity.create_registration_with_verification"
        ) as registration, patch(
            "app.api.v2.identity.reset_password"
        ) as reset, _client(db) as client:
            registration_response = client.post(
                "/api/v2/auth/registration-requests",
                json={
                    "email": "person@example.com",
                    "password": password,
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                },
            )
            reset_response = client.post(
                "/api/v2/auth/password-resets",
                json={"token": RAW_TOKEN, "new_password": password},
            )
        assert registration_response.status_code == 422
        assert reset_response.status_code == 422
        assert password not in registration_response.text
        assert password not in reset_response.text
        registration.assert_not_called()
        reset.assert_not_called()
        db.commit.assert_not_called()


def test_password_credential_hash_fields_are_forbidden() -> None:
    for field in ("hashed_password", "password_hash", "password_digest"):
        db = MagicMock()
        with _client(db) as client:
            registration = client.post(
                "/api/v2/auth/registration-requests",
                json={
                    "email": "person@example.com",
                    "password": "ValidPassword!",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    field: "hostile-value",
                },
            )
            reset = client.post(
                "/api/v2/auth/password-resets",
                json={
                    "token": RAW_TOKEN,
                    "new_password": "NewPassword!",
                    field: "hostile-value",
                },
            )
        assert registration.status_code == 422
        assert reset.status_code == 422
        assert "hostile-value" not in registration.text
        assert "hostile-value" not in reset.text


def test_invalid_reset_variants_share_safe_error() -> None:
    for private_reason in ("expired", "consumed", "revoked", "missing"):
        db = MagicMock()
        with patch(
            "app.api.v2.identity.reset_password",
            side_effect=InvalidPasswordResetTokenError(private_reason),
        ), _client(db) as client:
            response = client.post(
                "/api/v2/auth/password-resets",
                json={"token": RAW_TOKEN, "new_password": "NewPassword!"},
            )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_PASSWORD_RESET_TOKEN"
        assert private_reason not in response.text
        assert "NewPassword!" not in response.text
        db.rollback.assert_called_once_with()
        db.commit.assert_not_called()


def test_recovery_and_reset_reject_mass_assignment() -> None:
    forbidden = (
        ("user_id", str(uuid.uuid4())),
        ("account_status", "ACTIVE"),
        ("global_role", "GLOBAL_ADMIN"),
        ("token_type", "PASSWORD_RESET"),
        ("actor_user_id", str(uuid.uuid4())),
        ("owner_user_id", str(uuid.uuid4())),
    )
    for field, value in forbidden:
        db = MagicMock()
        with patch("app.api.v2.identity.request_password_recovery") as recovery, _client(db) as client:
            response = client.post(
                "/api/v2/auth/password-recovery-requests",
                json={"email": "person@example.com", field: value},
            )
        assert response.status_code == 422
        recovery.assert_not_called()

        with patch("app.api.v2.identity.reset_password") as reset, _client(db) as client:
            response = client.post(
                "/api/v2/auth/password-resets",
                json={
                    "token": RAW_TOKEN,
                    "new_password": "NewPassword!",
                    field: value,
                },
            )
        assert response.status_code == 422
        reset.assert_not_called()


def test_empty_and_oversized_reset_token_fail_safely() -> None:
    db = MagicMock()
    with _client(db) as client:
        empty = client.post(
            "/api/v2/auth/password-resets",
            json={"token": "", "new_password": "NewPassword!"},
        )
        oversized = client.post(
            "/api/v2/auth/password-resets",
            json={"token": "R" * 513, "new_password": "NewPassword!"},
        )
    assert empty.status_code == 422
    assert oversized.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unexpected_recovery_and_reset_failures_rollback_safely() -> None:
    for route, service_path, payload in (
        (
            "/api/v2/auth/password-recovery-requests",
            "app.api.v2.identity.request_password_recovery",
            {"email": "person@example.com"},
        ),
        (
            "/api/v2/auth/password-resets",
            "app.api.v2.identity.reset_password",
            {"token": RAW_TOKEN, "new_password": "NewPassword!"},
        ),
    ):
        db = MagicMock()
        with patch(service_path, side_effect=RuntimeError("private failure")), _client(
            db, raise_server_exceptions=False
        ) as client:
            response = client.post(route, json=payload)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "private failure" not in response.text
        db.rollback.assert_called_once_with()
        db.commit.assert_not_called()


def test_openapi_exposes_only_public_password_recovery_fields() -> None:
    openapi = app.openapi()
    assert {
        "/api/v2/auth/password-recovery-requests",
        "/api/v2/auth/password-resets",
    } <= set(openapi["paths"])
    schemas = openapi["components"]["schemas"]
    assert set(schemas["PasswordRecoveryRequest"]["properties"]) == {"email"}
    assert set(schemas["PasswordResetRequest"]["properties"]) == {
        "token",
        "new_password",
    }
    assert set(schemas["PasswordResetResponse"]["properties"]) == {
        "password_reset"
    }
    assert "token_digest" not in str(schemas)
    assert "hashed_password" not in str(schemas)
