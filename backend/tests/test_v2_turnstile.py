import json

from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_db
from app.api.v2.errors import V2APIError
from app.core.config import settings
from app.main import app
from app.services.anti_bot_service import (
    AntiBotProviderUnavailable,
    AntiBotVerificationFailed,
    CloudflareTurnstileVerifier,
)


class _Response:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode()


def _verifier() -> CloudflareTurnstileVerifier:
    return CloudflareTurnstileVerifier(secret_key="server-only-secret", timeout_seconds=3.0)


def test_cloudflare_adapter_accepts_success_and_uses_bounded_request() -> None:
    with patch(
        "app.services.anti_bot_service.urlopen",
        return_value=_Response(
            {"success": True, "hostname": "app.example", "action": "register"}
        ),
    ) as transport:
        _verifier().verify(token="ephemeral-client-token", remote_ip="2001:db8::1")

    request = transport.call_args.args[0]
    assert transport.call_args.kwargs["timeout"] == 3.0
    assert request.full_url.endswith("/turnstile/v0/siteverify")
    assert b"remoteip=2001%3Adb8%3A%3A1" in request.data


def test_cloudflare_adapter_distinguishes_invalid_challenge() -> None:
    with patch(
        "app.services.anti_bot_service.urlopen",
        return_value=_Response({"success": False, "error-codes": ["invalid-input-response"]}),
    ), pytest.raises(AntiBotVerificationFailed):
        _verifier().verify(token="invalid", remote_ip="192.0.2.1")


def test_replayed_token_is_rejected_when_provider_marks_second_use_invalid() -> None:
    with patch(
        "app.services.anti_bot_service.urlopen",
        side_effect=[_Response({"success": True}), _Response({"success": False})],
    ):
        _verifier().verify(token="single-use-token", remote_ip="192.0.2.1")
        with pytest.raises(AntiBotVerificationFailed):
            _verifier().verify(token="single-use-token", remote_ip="192.0.2.1")


@pytest.mark.parametrize(
    "provider_result",
    [
        HTTPError("https://provider.invalid", 500, "error", {}, None),
        URLError("timeout"),
        TimeoutError(),
        _Response(b"not-json"),
        _Response({"unexpected": True}),
        _Response({"success": True, "hostname": ["invalid"]}),
    ],
)
def test_cloudflare_adapter_maps_provider_failures_safely(provider_result: object) -> None:
    context = (
        patch("app.services.anti_bot_service.urlopen", side_effect=provider_result)
        if isinstance(provider_result, BaseException)
        else patch("app.services.anti_bot_service.urlopen", return_value=provider_result)
    )
    with context, pytest.raises(AntiBotProviderUnavailable):
        _verifier().verify(token="opaque", remote_ip="192.0.2.1")


PROTECTED = [
    (
        "/api/v2/auth/registration-requests",
        {
            "email": "person@example.com",
            "password": "ValidPassword!",
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    ),
    (
        "/api/v2/auth/password-recovery-requests",
        {"email": "person@example.com"},
    ),
    (
        "/api/v2/auth/email-verifications/resend",
        {"email": "person@example.com"},
    ),
]


def _client(db: MagicMock) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


@pytest.mark.parametrize(("path", "payload"), PROTECTED)
def test_protected_routes_require_valid_turnstile_before_domain_work(
    path: str, payload: dict[str, str]
) -> None:
    db = MagicMock()
    domain_names = (
        "create_registration_with_verification",
        "request_password_recovery",
        "resend_email_verification",
    )
    with patch.object(settings, "TURNSTILE_ENABLED", True), patch.object(
        settings, "TURNSTILE_SECRET_KEY", "server-only-secret"
    ), patch("app.api.v2.identity._enforce_rate_limit") as limiter, patch(
        "app.services.anti_bot_service.urlopen"
    ) as transport, patch("app.api.v2.identity.create_registration_with_verification") as registration, patch(
        "app.api.v2.identity.request_password_recovery"
    ) as recovery, patch(
        "app.api.v2.identity.resend_email_verification"
    ) as resend, _client(db) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ANTI_BOT_VERIFICATION_FAILED"
    limiter.assert_called_once()
    transport.assert_not_called()
    for domain in (registration, recovery, resend):
        domain.assert_not_called()
    db.commit.assert_not_called()
    assert domain_names


@pytest.mark.parametrize(("path", "payload"), PROTECTED)
def test_invalid_or_unavailable_turnstile_has_no_domain_or_email_side_effects(
    path: str, payload: dict[str, str]
) -> None:
    db = MagicMock()
    payload = {**payload, "turnstile_token": "opaque-client-token"}
    for error, expected_status, expected_code in (
        (AntiBotVerificationFailed(), 400, "ANTI_BOT_VERIFICATION_FAILED"),
        (AntiBotProviderUnavailable(), 503, "SECURITY_CONTROL_UNAVAILABLE"),
    ):
        with patch("app.api.v2.identity._enforce_rate_limit") as limiter, patch(
            "app.api.v2.identity.verify_anti_bot_token", side_effect=error
        ) as verifier, patch(
            "app.api.v2.identity.create_registration_with_verification"
        ) as registration, patch(
            "app.api.v2.identity.request_password_recovery"
        ) as recovery, patch(
            "app.api.v2.identity.resend_email_verification"
        ) as resend, patch(
            "app.api.v2.identity.email_delivery.send_verification_email"
        ) as verification_delivery, patch(
            "app.api.v2.identity.email_delivery.send_password_reset_email"
        ) as recovery_delivery, _client(db) as client:
            response = client.post(path, json=payload)

        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
        limiter.assert_called_once()
        verifier.assert_called_once()
        for domain in (registration, recovery, resend):
            domain.assert_not_called()
        verification_delivery.assert_not_called()
        recovery_delivery.assert_not_called()
        db.commit.assert_not_called()


@pytest.mark.parametrize(("path", "payload"), PROTECTED)
def test_valid_turnstile_allows_neutral_route_behavior(
    path: str, payload: dict[str, str]
) -> None:
    db = MagicMock()
    payload = {**payload, "turnstile_token": "opaque-client-token"}
    with patch("app.api.v2.identity._enforce_rate_limit") as limiter, patch(
        "app.api.v2.identity.verify_anti_bot_token"
    ) as verifier, patch(
        "app.api.v2.identity.resolve_client_ip", return_value="2001:db8::1"
    ), patch(
        "app.api.v2.identity.create_registration_with_verification", return_value=None
    ), patch(
        "app.api.v2.identity.request_password_recovery", return_value=None
    ), patch(
        "app.api.v2.identity.resend_email_verification", return_value=None
    ), _client(db) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    limiter.assert_called_once()
    verifier.assert_called_once_with(
        token="opaque-client-token", remote_ip="2001:db8::1"
    )
    db.commit.assert_called_once_with()


def test_rate_limit_rejection_occurs_before_turnstile() -> None:
    db = MagicMock()
    payload = {**PROTECTED[0][1], "turnstile_token": "opaque-client-token"}
    rate_error = V2APIError(429, "RATE_LIMITED", "safe")
    with patch(
        "app.api.v2.identity._enforce_rate_limit", side_effect=rate_error
    ), patch("app.api.v2.identity.verify_anti_bot_token") as verifier, patch(
        "app.api.v2.identity.create_registration_with_verification"
    ) as domain, _client(db) as client:
        response = client.post(PROTECTED[0][0], json=payload)

    assert response.status_code == 429
    verifier.assert_not_called()
    domain.assert_not_called()


def test_openapi_exposes_only_public_token_on_selected_routes() -> None:
    schema = app.openapi()
    protected_schema_names = {
        "RegistrationRequestCreate",
        "PasswordRecoveryRequest",
        "EmailVerificationResendRequest",
    }
    for name in protected_schema_names:
        properties = schema["components"]["schemas"][name]["properties"]
        assert "turnstile_token" in properties
        assert "secret" not in json.dumps(properties).lower()
    assert "turnstile_token" not in schema["components"]["schemas"]["LoginRequest"]["properties"]


def teardown_function() -> None:
    app.dependency_overrides.clear()
