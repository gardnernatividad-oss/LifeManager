import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db
from app.core.config import settings
from app.core.session_security import create_session_token, new_csrf_token
from app.main import app
from app.models import Workspace
from app.models.enums import AccountStatus, GlobalRole, WorkspaceKind


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _account(
    *,
    status: AccountStatus = AccountStatus.ACTIVE,
    global_admin: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="owner@example.com",
        hashed_password="fixture-hash",
        first_name="Ana",
        last_name="Pérez",
        timezone="America/Lima",
        account_status=status,
        global_role=GlobalRole.GLOBAL_ADMIN if global_admin else None,
    )


def _workspace(account: SimpleNamespace, name: str = "Familia") -> Workspace:
    return Workspace(
        id=uuid.uuid4(),
        name=name,
        kind=WorkspaceKind.SHARED,
        owner_user_id=account.id,
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


def test_active_user_creates_shared_workspace_and_route_owns_transaction() -> None:
    db = MagicMock()
    account = _account()
    workspace = _workspace(account, "Familia Pérez")
    with patch(
        "app.api.v2.workspaces.create_shared_workspace",
        return_value=workspace,
    ) as service, _client(db, account=account) as client:
        response = client.post(
            "/api/v2/workspaces",
            json={"name": "  Familia   Pérez  "},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(workspace.id),
        "name": "Familia Pérez",
        "kind": "SHARED",
    }
    assert service.call_args.kwargs["creator"] is account
    assert service.call_args.kwargs["workspace_in"].name == "Familia Pérez"
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(workspace)
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "account_status",
    [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.PENDING_APPROVAL,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ],
)
def test_non_active_accounts_cannot_create_shared_workspace(
    account_status: AccountStatus,
) -> None:
    db = MagicMock()
    with patch("app.api.v2.workspaces.create_shared_workspace") as service, _client(
        db, account=_account(status=account_status)
    ) as client:
        response = client.post("/api/v2/workspaces", json={"name": "Familia"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION"
    service.assert_not_called()
    db.commit.assert_not_called()


def test_anonymous_user_cannot_create_shared_workspace() -> None:
    db = MagicMock()
    with _client(db) as client:
        response = client.post("/api/v2/workspaces", json={"name": "Familia"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION"
    db.commit.assert_not_called()


def test_global_admin_creates_only_owned_shared_workspace() -> None:
    db = MagicMock()
    admin = _account(global_admin=True)
    workspace = _workspace(admin)
    with patch(
        "app.api.v2.workspaces.create_shared_workspace",
        return_value=workspace,
    ) as service, _client(db, account=admin) as client:
        response = client.post("/api/v2/workspaces", json={"name": "Familia"})

    assert response.status_code == 201
    assert service.call_args.kwargs["creator"] is admin
    assert response.json()["kind"] == "SHARED"


@pytest.mark.parametrize(
    "field",
    [
        "kind", "owner_user_id", "user_id", "status", "role",
        "global_role", "created_at", "updated_at", "lock_version",
        "members", "owner",
    ],
)
def test_route_rejects_workspace_mass_assignment(field: str) -> None:
    db = MagicMock()
    account = _account()
    with patch("app.api.v2.workspaces.create_shared_workspace") as service, _client(
        db, account=account
    ) as client:
        response = client.post(
            "/api/v2/workspaces",
            json={"name": "Familia", field: "hostile"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "hostile" not in response.text
    service.assert_not_called()
    db.commit.assert_not_called()


def test_creation_failure_rolls_back_with_safe_error() -> None:
    db = MagicMock()
    account = _account()
    with patch(
        "app.api.v2.workspaces.create_shared_workspace",
        side_effect=RuntimeError("private constraint detail"),
    ), _client(db, account=account, raise_server_exceptions=False) as client:
        response = client.post("/api/v2/workspaces", json={"name": "Familia"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "constraint" not in response.text
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_authenticated_mutation_requires_existing_csrf_protection() -> None:
    db = MagicMock()
    account = _account()
    csrf_token = new_csrf_token()
    session_token = create_session_token(
        user_id=account.id,
        hashed_password=account.hashed_password,
        csrf_token=csrf_token,
    )
    with _client(db, account=account) as client:
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_token)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
        response = client.post(
            "/api/v2/workspaces",
            json={"name": "Familia"},
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    db.commit.assert_not_called()


def test_valid_session_and_csrf_can_create_shared_workspace() -> None:
    db = MagicMock()
    account = _account()
    workspace = _workspace(account)
    db.scalar.return_value = account
    csrf_token = new_csrf_token()
    session_token = create_session_token(
        user_id=account.id,
        hashed_password=account.hashed_password,
        csrf_token=csrf_token,
    )
    with patch(
        "app.api.v2.workspaces.create_shared_workspace",
        return_value=workspace,
    ), _client(db) as client:
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_token)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
        response = client.post(
            "/api/v2/workspaces",
            json={"name": "Familia"},
            headers={
                "Origin": "http://localhost:5173",
                settings.CSRF_HEADER_NAME: csrf_token,
            },
        )

    assert response.status_code == 201
    db.commit.assert_called_once_with()


def test_openapi_workspace_creation_is_allowlisted() -> None:
    openapi = app.openapi()
    operation = openapi["paths"]["/api/v2/workspaces"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"].rsplit("/", 1)[-1]
    response_schema = operation["responses"]["201"]["content"][
        "application/json"
    ]["schema"]["$ref"].rsplit("/", 1)[-1]
    schemas = openapi["components"]["schemas"]

    assert set(schemas[request_schema]["properties"]) == {"name"}
    assert schemas[request_schema]["additionalProperties"] is False
    assert set(schemas[response_schema]["properties"]) == {"id", "name", "kind"}
    serialized = str(operation)
    for forbidden in (
        "owner_user_id", "global_role", "lock_version", "members",
    ):
        assert forbidden not in serialized
