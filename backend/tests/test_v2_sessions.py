import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_db
from app.core.config import settings
from app.core.session_security import create_session_token, new_csrf_token
from app.main import app
from app.models import User
from app.models.enums import AccountStatus, GlobalRole
from app.services.session_service import InvalidCredentialsError


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _user(
    *,
    status: AccountStatus = AccountStatus.ACTIVE,
    role: GlobalRole | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        hashed_password="$argon2id$credential-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        global_role=role,
        email_verified_at=NOW,
        status_changed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        lock_version=1,
    )


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(db: MagicMock):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with patch("app.api.v2.identity._enforce_rate_limit"), TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _install_session(client: TestClient, user: User) -> str:
    csrf = new_csrf_token()
    token = create_session_token(
        user_id=user.id,
        hashed_password=user.hashed_password,
        status_changed_at=user.status_changed_at,
        csrf_token=csrf,
    )
    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf)
    return csrf


def test_login_sets_fresh_securely_scoped_cookies_without_returning_token(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    with patch("app.api.v2.identity.authenticate_session", return_value=user):
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "PERSON@example.com", "password": "ValidPassword!"},
        )
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert "token" not in response.text.lower()
    cookies = response.headers.get_list("set-cookie")
    session = next(value for value in cookies if settings.SESSION_COOKIE_NAME in value)
    csrf = next(value for value in cookies if settings.CSRF_COOKIE_NAME in value)
    assert "HttpOnly" in session
    assert "Path=/" in session
    assert "SameSite=lax" in session
    assert "Max-Age=28800" in session
    assert "HttpOnly" not in csrf
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)


def test_login_rotates_session_and_csrf_material(
    client: TestClient,
) -> None:
    user = _user()
    with patch("app.api.v2.identity.authenticate_session", return_value=user):
        first = client.post(
            "/api/v2/auth/login",
            json={"email": user.email, "password": "ValidPassword!"},
        )
        first_session = client.cookies.get(settings.SESSION_COOKIE_NAME)
        first_csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
        second = client.post(
            "/api/v2/auth/login",
            json={"email": user.email, "password": "ValidPassword!"},
        )
    assert first.status_code == second.status_code == 200
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) != first_session
    assert client.cookies.get(settings.CSRF_COOKIE_NAME) != first_csrf


def test_production_cookie_override_enforces_secure(
    client: TestClient,
) -> None:
    user = _user()
    with patch.object(settings, "SESSION_COOKIE_SECURE", True), patch(
        "app.api.v2.identity.authenticate_session",
        return_value=user,
    ):
        response = client.post(
            "/api/v2/auth/login",
            json={"email": user.email, "password": "ValidPassword!"},
        )
    cookies = response.headers.get_list("set-cookie")
    assert all("Secure" in value for value in cookies)


@pytest.mark.parametrize(
    "reason",
    ["unknown", "wrong", "pending", "rejected", "disabled"],
)
def test_login_failures_are_neutral(
    reason: str,
    client: TestClient,
    db: MagicMock,
) -> None:
    with patch(
        "app.api.v2.identity.authenticate_session",
        side_effect=InvalidCredentialsError(reason),
    ):
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "person@example.com", "password": "WrongPassword!"},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert reason not in response.text
    db.rollback.assert_called_once_with()


def test_me_checks_current_hash_and_active_state(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    db.scalar.return_value = user
    _install_session(client, user)
    valid = client.get("/api/v2/me")
    assert valid.status_code == 200
    assert set(valid.json()) == {
        "id", "email", "first_name", "last_name", "timezone", "global_role"
    }

    user.hashed_password = "$argon2id$new-credential-hash"
    assert client.get("/api/v2/me").status_code == 401


def test_disabled_session_does_not_revive_after_account_reactivation(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    db.scalar.return_value = user
    _install_session(client, user)
    assert client.get("/api/v2/me").status_code == 200

    user.account_status = AccountStatus.DISABLED
    user.status_changed_at = NOW + timedelta(minutes=1)
    assert client.get("/api/v2/me").status_code == 401

    user.account_status = AccountStatus.ACTIVE
    user.status_changed_at = NOW + timedelta(minutes=2)
    assert client.get("/api/v2/me").status_code == 401

    _install_session(client, user)
    assert client.get("/api/v2/me").status_code == 200
    user.account_status = AccountStatus.DISABLED
    assert client.get("/api/v2/me").status_code == 401


def test_expired_forged_and_wrong_purpose_sessions_are_rejected(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    db.scalar.return_value = user
    csrf = new_csrf_token()
    expired = create_session_token(
        user_id=user.id,
        hashed_password=user.hashed_password,
        status_changed_at=user.status_changed_at,
        csrf_token=csrf,
        now=datetime.now(timezone.utc) - timedelta(days=1),
    )
    for token in (
        expired,
        "malformed",
        jwt.encode(
            {
                "sub": str(user.id), "iat": NOW, "exp": NOW + timedelta(hours=1),
                "type": "access", "cv": "x", "csrf": "y",
            },
            "another-secret-key-that-is-at-least-32-bytes",
            algorithm="HS256",
        ),
    ):
        client.cookies.set(settings.SESSION_COOKIE_NAME, token)
        assert client.get("/api/v2/me").status_code == 401


def test_csrf_and_origin_protect_authenticated_admin_mutations(
    client: TestClient,
    db: MagicMock,
) -> None:
    admin = _user(role=GlobalRole.GLOBAL_ADMIN)
    target = _user(status=AccountStatus.PENDING_APPROVAL)
    db.scalar.return_value = admin
    csrf = _install_session(client, admin)
    path = f"/api/v2/admin/account-requests/{target.id}/approve"
    assert client.post(path).status_code == 403
    assert client.post(path, headers={"Origin": "http://malicious.example", settings.CSRF_HEADER_NAME: csrf}).status_code == 403
    assert client.post(path, headers={"Origin": "http://localhost:5173", settings.CSRF_HEADER_NAME: "wrong"}).status_code == 403
    client.cookies.set(settings.CSRF_COOKIE_NAME, "attacker-controlled")
    assert client.post(path, headers={"Origin": "http://localhost:5173", settings.CSRF_HEADER_NAME: "attacker-controlled"}).status_code == 403
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf)
    with patch(
        "app.api.v2.identity.approve_registration_request",
        return_value=target,
    ):
        allowed = client.post(
            path,
            headers={"Origin": "http://localhost:5173", settings.CSRF_HEADER_NAME: csrf},
        )
    assert allowed.status_code == 200


def test_csrf_from_a_prior_session_is_rejected(
    client: TestClient,
    db: MagicMock,
) -> None:
    admin = _user(role=GlobalRole.GLOBAL_ADMIN)
    target = _user(status=AccountStatus.PENDING_APPROVAL)
    db.scalar.return_value = admin
    stale_csrf = _install_session(client, admin)
    _install_session(client, admin)
    client.cookies.set(settings.CSRF_COOKIE_NAME, stale_csrf)

    response = client.post(
        f"/api/v2/admin/account-requests/{target.id}/approve",
        headers={
            "Origin": "http://localhost:5173",
            settings.CSRF_HEADER_NAME: stale_csrf,
        },
    )

    assert response.status_code == 403
    db.commit.assert_not_called()


def test_global_admin_role_is_authoritative_for_an_existing_session(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user(role=GlobalRole.GLOBAL_ADMIN)
    csrf = _install_session(client, user)
    user.global_role = None
    db.scalar.return_value = user

    response = client.post(
        f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve",
        headers={
            "Origin": "http://localhost:5173",
            settings.CSRF_HEADER_NAME: csrf,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "GLOBAL_ADMIN_REQUIRED"
    db.commit.assert_not_called()


def test_logout_is_csrf_protected_and_deletes_both_cookies(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    csrf = _install_session(client, user)
    assert client.post("/api/v2/auth/logout").status_code == 403
    response = client.post(
        "/api/v2/auth/logout",
        headers={"Origin": "http://localhost:5173", settings.CSRF_HEADER_NAME: csrf},
    )
    assert response.status_code == 204
    cookies = response.headers.get_list("set-cookie")
    assert all("Max-Age=0" in value and "Path=/" in value for value in cookies)


def test_authenticated_password_change_requires_csrf(
    client: TestClient,
    db: MagicMock,
) -> None:
    user = _user()
    db.scalar.return_value = user
    _install_session(client, user)
    response = client.post(
        "/api/v2/configuration/password",
        json={
            "current_password": "CurrentPassword!",
            "new_password": "NewPassword!",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_admin_account_state_change_requires_csrf(
    client: TestClient,
    db: MagicMock,
) -> None:
    admin = _user(role=GlobalRole.GLOBAL_ADMIN)
    db.scalar.return_value = admin
    _install_session(client, admin)
    response = client.post(
        f"/api/v2/admin/users/{uuid.uuid4()}/disable",
        json={"lock_version": 1},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_credentialed_cors_is_explicit(client: TestClient) -> None:
    allowed = client.options(
        "/api/v2/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": settings.CSRF_HEADER_NAME,
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = client.options(
        "/api/v2/auth/login",
        headers={
            "Origin": "http://malicious.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_describes_cookie_auth_and_never_returns_session_token() -> None:
    openapi = app.openapi()
    schemes = openapi["components"]["securitySchemes"]
    assert schemes["APIKeyCookie"]["in"] == "cookie"
    assert schemes["APIKeyCookie"]["name"] == settings.SESSION_COOKIE_NAME
    login_schema = openapi["components"]["schemas"]["AuthenticatedAccountRead"]
    serialized = str(login_schema)
    assert "access_token" not in serialized
    assert settings.SECRET_KEY not in str(openapi)
