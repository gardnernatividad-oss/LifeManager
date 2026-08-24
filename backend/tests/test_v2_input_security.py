import uuid

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v2.dependencies import get_current_account, get_db
from app.core.config import Settings
from app.core.session_security import decode_session_token
from app.main import app
from app.models.enums import AccountStatus, GlobalRole
from app.schemas.v2_identity import (
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    LoginRequest,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    RegistrationRequestCreate,
    RejectAccountRequest,
)


WRITE_DTOS = (
    (
        RegistrationRequestCreate,
        {
            "email": "person@example.com",
            "password": "ValidPassword!",
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    ),
    (LoginRequest, {"email": "person@example.com", "password": "Password!"}),
    (EmailVerificationRequest, {"token": "T" * 43}),
    (EmailVerificationResendRequest, {"email": "person@example.com"}),
    (PasswordRecoveryRequest, {"email": "person@example.com"}),
    (
        PasswordResetRequest,
        {"token": "T" * 43, "new_password": "NewPassword!"},
    ),
    (RejectAccountRequest, {"reason": "Not approved"}),
)

PRIVILEGED_FIELDS = (
    "id",
    "user_id",
    "actor_user_id",
    "created_by",
    "resolved_by",
    "account_status",
    "global_role",
    "owner_user_id",
    "workspace_id",
    "membership_role",
    "membership_status",
    "email_verified_at",
    "approval_metadata",
    "hashed_password",
    "token_digest",
    "lock_version",
    "created_at",
    "updated_at",
)


@pytest.mark.parametrize(("dto", "valid_payload"), WRITE_DTOS)
def test_every_v2_write_dto_forbids_privileged_mass_assignment(
    dto: type,
    valid_payload: dict[str, object],
) -> None:
    assert dto.model_config.get("extra") == "forbid"
    for field in PRIVILEGED_FIELDS:
        with pytest.raises(ValidationError):
            dto.model_validate({**valid_payload, field: "hostile-value"})


@pytest.mark.parametrize(
    ("path", "payload"),
    (
        (
            "/api/v2/auth/login",
            {"email": "person@example.com", "password": "Password!"},
        ),
        ("/api/v2/auth/email-verifications", {"token": "T" * 43}),
        (
            "/api/v2/auth/email-verifications/resend",
            {"email": "person@example.com"},
        ),
        (
            "/api/v2/auth/password-recovery-requests",
            {"email": "person@example.com"},
        ),
        (
            "/api/v2/auth/password-resets",
            {"token": "T" * 43, "new_password": "NewPassword!"},
        ),
    ),
)
def test_public_v2_routes_reject_privileged_fields_without_echoing_values(
    path: str,
    payload: dict[str, object],
) -> None:
    db = MagicMock()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("app.api.v2.identity._enforce_rate_limit"), TestClient(app) as client:
            response = client.post(
                path,
                json={**payload, "global_role": "GLOBAL_ADMIN"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "GLOBAL_ADMIN" not in response.text
    db.commit.assert_not_called()


def test_identity_lengths_and_control_characters_fail_before_service_work() -> None:
    db = MagicMock()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("app.api.v2.identity._enforce_rate_limit"), patch(
            "app.api.v2.identity.create_registration_with_verification"
        ) as service, TestClient(app) as client:
            responses = (
                client.post(
                    "/api/v2/auth/registration-requests",
                    json={
                        "email": f"{'a' * 245}@example.com",
                        "password": "ValidPassword!",
                        "first_name": "Ada",
                        "last_name": "Lovelace",
                    },
                ),
                client.post(
                    "/api/v2/auth/registration-requests",
                    json={
                        "email": "person@example.com",
                        "password": "ValidPassword!",
                        "first_name": "Ada\nInjected",
                        "last_name": "Lovelace",
                    },
                ),
            )
    finally:
        app.dependency_overrides.clear()

    assert all(response.status_code == 422 for response in responses)
    assert all("Injected" not in response.text for response in responses)
    service.assert_not_called()


def test_sensitive_validation_inputs_are_never_reflected() -> None:
    db = MagicMock()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    cases = (
        (
            "/api/v2/auth/login",
            {"email": "person@example.com", "password": "P" * 129},
            "P" * 129,
        ),
        (
            "/api/v2/auth/email-verifications",
            {"token": "V" * 513},
            "V" * 513,
        ),
        (
            "/api/v2/auth/password-resets",
            {"token": "R" * 513, "new_password": "NewPassword!"},
            "R" * 513,
        ),
        (
            "/api/v2/auth/registration-requests",
            {
                "email": "person@example.com",
                "password": "ValidPassword!",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "turnstile_token": "C" * 2049,
            },
            "C" * 2049,
        ),
    )
    try:
        with patch("app.api.v2.identity._enforce_rate_limit"), TestClient(app) as client:
            responses = [
                (client.post(path, json=payload), secret)
                for path, payload, secret in cases
            ]
    finally:
        app.dependency_overrides.clear()

    for response, secret in responses:
        assert response.status_code == 422
        assert secret not in response.text


def test_malformed_content_types_and_json_fail_without_internal_details() -> None:
    with patch("app.api.v2.identity._enforce_rate_limit"), TestClient(
        app, raise_server_exceptions=False
    ) as client:
        responses = (
            client.post(
                "/api/v2/auth/login",
                content="not-json",
                headers={"Content-Type": "application/json"},
            ),
            client.post(
                "/api/v2/auth/login",
                content="email=person@example.com&password=Password!",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            client.post(
                "/api/v2/auth/login",
                content="plain text",
                headers={"Content-Type": "text/plain"},
            ),
        )
    assert all(response.status_code == 422 for response in responses)
    assert all(response.json()["error"]["code"] == "VALIDATION_ERROR" for response in responses)
    assert all("person@example.com" not in response.text for response in responses)


def test_oversized_session_token_is_rejected_before_jwt_decode() -> None:
    with patch("app.core.session_security.jwt.decode") as decoder:
        assert decode_session_token("x" * 4097) is None
    decoder.assert_not_called()


def test_settings_repr_redacts_configured_secrets() -> None:
    secret_key = "s" * 32
    settings = Settings(
        DATABASE_URL="postgresql://user:private-password@localhost/lifemanager",
        SECRET_KEY=secret_key,
        RATE_LIMIT_HMAC_KEY="r" * 32,
        TURNSTILE_SECRET_KEY="turnstile-private",
    )
    rendered = repr(settings)
    assert "private-password" not in rendered
    assert secret_key not in rendered
    assert "turnstile-private" not in rendered
    assert "r" * 32 not in rendered


def test_openapi_response_schemas_do_not_expose_security_fields() -> None:
    document = app.openapi()
    forbidden = {
        "hashed_password",
        "password_hash",
        "token_digest",
        "key_digest",
        "session_token",
        "csrf_digest",
    }
    response_schema_names: set[str] = set()
    for path_item in document["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in operation.get("responses", {}).values():
                schema = (
                    response.get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                reference = schema.get("$ref")
                if reference:
                    response_schema_names.add(reference.rsplit("/", 1)[-1])
    schemas = document["components"]["schemas"]
    for name in response_schema_names:
        assert forbidden.isdisjoint(schemas[name].get("properties", {}))


def test_admin_rejection_treats_html_and_sql_metacharacters_as_literal_text() -> None:
    db = MagicMock()
    admin = SimpleNamespace(
        id=uuid.uuid4(),
        global_role=GlobalRole.GLOBAL_ADMIN,
        account_status=AccountStatus.ACTIVE,
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_account] = lambda: admin
    hostile = "<script>alert('x')</script>'; DROP TABLE users;--"
    target = SimpleNamespace(
        id=uuid.uuid4(),
        email="person@example.com",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=AccountStatus.REJECTED,
        email_verified_at=None,
        created_at="2026-08-24T12:00:00Z",
    )
    try:
        with patch("app.api.v2.identity._enforce_rate_limit"), patch(
            "app.api.v2.identity.reject_registration_request",
            return_value=target,
        ) as service, TestClient(app) as client:
            response = client.post(
                f"/api/v2/admin/account-requests/{target.id}/reject",
                json={"reason": hostile},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert hostile not in response.text
    assert service.call_args.kwargs["reason"] == hostile

