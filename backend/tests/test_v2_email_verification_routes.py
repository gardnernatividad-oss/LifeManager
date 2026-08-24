import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_db
from app.main import app
from app.services.email_verification_service import (
    InvalidEmailVerificationTokenError,
    IssuedEmailVerification,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
RAW_TOKEN = "A" * 43


def _client(db: MagicMock, *, raise_server_exceptions: bool = True) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_public_verification_commits_once_and_returns_minimal_response() -> None:
    db = MagicMock()
    with patch("app.api.v2.identity.verify_email_token") as service, _client(db) as client:
        response = client.post(
            "/api/v2/auth/email-verifications",
            json={"token": RAW_TOKEN},
        )

    assert response.status_code == 200
    assert response.json() == {"verified": True, "pending_approval": True}
    service.assert_called_once_with(db, raw_token=RAW_TOKEN)
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


def test_registration_token_issuance_failure_rolls_back_without_delivery() -> None:
    db = MagicMock()
    payload = {
        "email": "person@example.com",
        "password": "ValidPassword!",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    with patch(
        "app.api.v2.identity.create_registration_with_verification",
        side_effect=RuntimeError("token persistence failed"),
    ), patch(
        "app.api.v2.identity.email_delivery.send_verification_email"
    ) as delivery, _client(db, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v2/auth/registration-requests",
            json=payload,
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "token persistence" not in response.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()
    delivery.assert_not_called()


def test_invalid_token_variants_share_safe_error() -> None:
    for private_reason in ("expired", "consumed", "revoked", "missing"):
        db = MagicMock()
        with patch(
            "app.api.v2.identity.verify_email_token",
            side_effect=InvalidEmailVerificationTokenError(private_reason),
        ), _client(db) as client:
            response = client.post(
                "/api/v2/auth/email-verifications",
                json={"token": RAW_TOKEN},
            )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_EMAIL_VERIFICATION_TOKEN"
        assert private_reason not in response.text
        db.rollback.assert_called_once_with()
        db.commit.assert_not_called()


def test_verification_rejects_privilege_fields_before_service() -> None:
    for field, value in (
        ("user_id", str(uuid.uuid4())),
        ("email", "person@example.com"),
        ("account_status", "ACTIVE"),
        ("global_role", "GLOBAL_ADMIN"),
        ("verified_at", NOW.isoformat()),
        ("token_type", "EMAIL_VERIFICATION"),
        ("actor_user_id", str(uuid.uuid4())),
    ):
        db = MagicMock()
        with patch("app.api.v2.identity.verify_email_token") as service, _client(db) as client:
            response = client.post(
                "/api/v2/auth/email-verifications",
                json={"token": RAW_TOKEN, field: value},
            )
        assert response.status_code == 422
        service.assert_not_called()


def test_empty_and_oversized_tokens_fail_safely() -> None:
    db = MagicMock()
    with _client(db) as client:
        empty = client.post("/api/v2/auth/email-verifications", json={"token": ""})
        oversized = client.post(
            "/api/v2/auth/email-verifications",
            json={"token": "A" * 513},
        )
    assert empty.status_code == 422
    assert oversized.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"


def test_resend_is_neutral_and_delivers_only_when_issued() -> None:
    issued = IssuedEmailVerification(
        recipient="person@example.com",
        raw_token=RAW_TOKEN,
        expires_at=NOW,
    )
    for service_result, expected_deliveries in ((issued, 1), (None, 0)):
        db = MagicMock()
        with patch(
            "app.api.v2.identity.resend_email_verification",
            return_value=service_result,
        ) as service, patch(
            "app.api.v2.identity.email_delivery.send_verification_email"
        ) as delivery, _client(db) as client:
            response = client.post(
                "/api/v2/auth/email-verifications/resend",
                json={"email": " Person@Example.com "},
            )
        assert response.status_code == 202
        assert response.json() == {"accepted": True}
        assert service.call_args.kwargs["email"] == "person@example.com"
        assert delivery.call_count == expected_deliveries
        db.commit.assert_called_once_with()
        db.rollback.assert_not_called()


def test_resend_rejects_unapproved_fields() -> None:
    db = MagicMock()
    with patch("app.api.v2.identity.resend_email_verification") as service, _client(db) as client:
        response = client.post(
            "/api/v2/auth/email-verifications/resend",
            json={"email": "person@example.com", "user_id": str(uuid.uuid4())},
        )
    assert response.status_code == 422
    service.assert_not_called()


def test_unexpected_verification_failure_rolls_back() -> None:
    db = MagicMock()
    with patch(
        "app.api.v2.identity.verify_email_token",
        side_effect=RuntimeError("private token detail"),
    ), _client(db, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v2/auth/email-verifications",
            json={"token": RAW_TOKEN},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private token detail" not in response.text
    db.rollback.assert_called_once_with()


def test_openapi_exposes_raw_token_only_in_verification_request() -> None:
    openapi = app.openapi()
    assert {
        "/api/v2/auth/email-verifications",
        "/api/v2/auth/email-verifications/resend",
    } <= set(openapi["paths"])
    schemas = openapi["components"]["schemas"]
    assert set(schemas["EmailVerificationRequest"]["properties"]) == {"token"}
    assert set(schemas["EmailVerificationResendRequest"]["properties"]) == {"email"}
    assert set(schemas["EmailVerificationResponse"]["properties"]) == {
        "verified",
        "pending_approval",
    }
    serialized_responses = str(
        {
            name: schema
            for name, schema in schemas.items()
            if name.endswith("Response") or name.endswith("Acknowledgement")
        }
    )
    assert "token" not in serialized_responses
    assert "token_digest" not in str(schemas)
    assert "hashed_password" not in str(schemas)
