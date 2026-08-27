import uuid

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_db
from app.core.config import settings
from app.core.session_security import create_session_token, new_csrf_token
from app.main import app
from app.models.enums import AccountStatus


NOW = datetime.now(timezone.utc)


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="person@example.com",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=None,
        hashed_password="$argon2id$fixture-current-hash",
    )


@pytest.fixture
def client_and_db():
    db = MagicMock()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with patch("app.api.v2.identity._enforce_rate_limit"), TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()


def _encoded(payload: dict[str, object], *, key: str | None = None) -> str:
    return jwt.encode(
        payload,
        key or settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def test_session_forgery_matrix_returns_the_same_neutral_401(client_and_db) -> None:
    client, db = client_and_db
    user = _user()
    db.scalar.return_value = user
    valid_claims = {
        "sub": str(user.id),
        "iat": NOW,
        "exp": NOW + timedelta(hours=1),
        "type": "session",
        "cv": "credential-version",
        "csrf": "csrf-digest",
    }
    variants = (
        "malformed",
        "x" * 4097,
        _encoded(valid_claims, key="different-signing-key-that-is-long-enough"),
        _encoded({key: value for key, value in valid_claims.items() if key != "exp"}),
        _encoded({**valid_claims, "exp": NOW - timedelta(seconds=1)}),
        _encoded({**valid_claims, "sub": "not-a-uuid"}),
        _encoded({**valid_claims, "type": "access"}),
        _encoded({**valid_claims, "cv": ""}),
        _encoded({**valid_claims, "csrf": ""}),
    )

    responses = []
    for token in variants:
        client.cookies.set(settings.SESSION_COOKIE_NAME, token)
        responses.append(client.get("/api/v2/me"))

    assert all(response.status_code == 401 for response in responses)
    assert all(response.json()["error"]["code"] == "INVALID_SESSION" for response in responses)
    assert all("traceback" not in response.text.lower() for response in responses)
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_oversized_csrf_values_fail_before_authenticated_mutation(client_and_db) -> None:
    client, db = client_and_db
    user = _user()
    db.scalar.return_value = user
    csrf = new_csrf_token()
    session = create_session_token(
        user_id=user.id,
        hashed_password=user.hashed_password,
        csrf_token=csrf,
    )
    client.cookies.set(settings.SESSION_COOKIE_NAME, session)
    client.cookies.set(settings.CSRF_COOKIE_NAME, "c" * 513)

    response = client.post(
        f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve",
        headers={
            "Origin": "http://localhost:5173",
            settings.CSRF_HEADER_NAME: "c" * 513,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_registration_rejects_nested_privileged_payload(client_and_db) -> None:
    client, db = client_and_db
    with patch("app.api.v2.identity.create_registration_with_verification") as service:
        response = client.post(
            "/api/v2/auth/registration-requests",
            json={
                "email": "person@example.com",
                "password": "ValidPassword!",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "workspace": {
                    "owner_user_id": str(uuid.uuid4()),
                    "membership_role": "OWNER",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "owner_user_id" not in response.text
    service.assert_not_called()
    db.commit.assert_not_called()


def test_v2_openapi_exposes_only_the_approved_attack_surface() -> None:
    document = app.openapi()
    v2_paths = {path for path in document["paths"] if path.startswith("/api/v2")}
    assert v2_paths == {
        "/api/v2/auth/login",
        "/api/v2/me",
        "/api/v2/auth/logout",
        "/api/v2/auth/registration-requests",
        "/api/v2/auth/email-verifications",
        "/api/v2/auth/email-verifications/resend",
        "/api/v2/auth/password-recovery-requests",
        "/api/v2/auth/password-resets",
        "/api/v2/admin/account-requests",
        "/api/v2/admin/account-requests/{user_id}",
        "/api/v2/admin/account-requests/{user_id}/approve",
        "/api/v2/admin/account-requests/{user_id}/reject",
            "/api/v2/workspaces",
            "/api/v2/workspaces/management",
        "/api/v2/workspaces/{workspace_id}/invitations",
        "/api/v2/workspace-invitations",
        "/api/v2/workspace-invitations/{invitation_id}/accept",
        "/api/v2/workspace-invitations/{invitation_id}/reject",
        "/api/v2/workspace-invitations/{invitation_id}/cancel",
        "/api/v2/workspaces/{workspace_id}/members",
        "/api/v2/workspaces/{workspace_id}/members/{user_id}",
        "/api/v2/workspaces/{workspace_id}/leave",
        "/api/v2/workspaces/{workspace_id}",
        "/api/v2/workspaces/{workspace_id}/lifecycle",
            "/api/v2/workspaces/{workspace_id}/deactivate",
            "/api/v2/workspaces/{workspace_id}/reactivate",
        "/api/v2/workspaces/{workspace_id}/transfer-ownership",
        "/api/v2/workspaces/{workspace_id}/categories",
        "/api/v2/workspaces/{workspace_id}/categories/{category_id}",
        "/api/v2/workspaces/{workspace_id}/categories/{category_id}/activate",
        "/api/v2/workspaces/{workspace_id}/categories/{category_id}/deactivate",
        "/api/v2/workspaces/{workspace_id}/master-tasks",
        "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}",
        "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}/activate",
        "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}/deactivate",
        "/api/v2/workspaces/{workspace_id}/activity-masters",
        "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}",
        "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}/activate",
        "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}/deactivate",
        "/api/v2/workspaces/{workspace_id}/selectors/categories",
        "/api/v2/workspaces/{workspace_id}/selectors/tasks",
            "/api/v2/workspaces/{workspace_id}/selectors/activities",
            "/api/v2/workspaces/{workspace_id}/tasks",
            "/api/v2/workspaces/{workspace_id}/tasks/{task_id}",
            "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/complete",
            "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/not-complete",
            "/api/v2/workspaces/{workspace_id}/tasks/recurring",
            "/api/v2/workspaces/{workspace_id}/pending-items",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/progress",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/correction",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/deactivate",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/reactivate",
            "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/history",
        }
    serialized = str(document).lower()
    for forbidden in (
        "hashed_password",
        "password_hash",
        "token_digest",
        "key_digest",
        "database_url",
        "turnstile_secret_key",
        "rate_limit_hmac_key",
    ):
        assert forbidden not in serialized
    assert not any(
        marker in path
        for path in v2_paths
        for marker in ("debug", "config", "tokens", "account-state-events")
    )
