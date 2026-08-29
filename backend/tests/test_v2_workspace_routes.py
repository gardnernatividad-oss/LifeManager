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
from app.models.enums import AccountStatus, GlobalRole, WorkspaceKind, WorkspaceLifecycle
from app.services.v2_workspace import WorkspaceAccess


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


def test_active_and_management_workspace_listings_are_explicit_and_read_only() -> None:
    db = MagicMock()
    account = _account()
    personal = _workspace(account, "Personal")
    personal.kind = WorkspaceKind.PERSONAL
    personal.lifecycle = WorkspaceLifecycle.ACTIVE
    shared = _workspace(account, "Familia")
    shared.lifecycle = WorkspaceLifecycle.INACTIVE
    personal_access = WorkspaceAccess(
        workspace=personal,
        membership=SimpleNamespace(user_id=account.id),
    )
    shared_access = WorkspaceAccess(
        workspace=shared,
        membership=SimpleNamespace(user_id=account.id),
    )
    with patch(
        "app.api.v2.workspaces.list_active_workspaces",
        return_value=[personal_access],
    ), patch(
        "app.api.v2.workspaces.list_manageable_workspaces",
        return_value=[personal_access, shared_access],
    ), patch(
        "app.api.v2.workspaces.workspace_can_be_hard_deleted",
        return_value=False,
    ), _client(db, account=account) as client:
        active = client.get("/api/v2/workspaces")
        management = client.get("/api/v2/workspaces/management")

    assert active.status_code == 200
    assert [item["kind"] for item in active.json()] == ["PERSONAL"]
    assert management.status_code == 200
    assert [item["lifecycle"] for item in management.json()] == ["ACTIVE", "INACTIVE"]
    assert management.json()[1]["visible_role"] == "Propietario"
    assert management.json()[1]["can_manage"] is True
    assert management.json()[1]["can_delete"] is False
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.flush.assert_not_called()


def test_openapi_has_one_authoritative_workspace_route_inventory() -> None:
    methods = {"get", "post", "put", "patch", "delete"}
    operations = {
        (method.upper(), path)
        for path, path_item in app.openapi()["paths"].items()
        if path.startswith("/api/v2/workspace")
        for method in path_item
        if method in methods
    }

    assert operations == {
        ("GET", "/api/v2/workspaces"),
            ("GET", "/api/v2/workspaces/management"),
            ("GET", "/api/v2/workspaces/{workspace_id}/calendar-comparison"),
            ("GET", "/api/v2/workspaces/{workspace_id}/calendar-comparison/multi"),
            ("GET", "/api/v2/workspaces/{workspace_id}/calendar-visibility"),
            ("PATCH", "/api/v2/workspaces/{workspace_id}/calendar-visibility"),
        ("POST", "/api/v2/workspaces"),
        ("GET", "/api/v2/workspaces/{workspace_id}/members"),
        ("DELETE", "/api/v2/workspaces/{workspace_id}/members/{user_id}"),
        ("POST", "/api/v2/workspaces/{workspace_id}/leave"),
        ("POST", "/api/v2/workspaces/{workspace_id}/invitations"),
        ("GET", "/api/v2/workspaces/{workspace_id}/invitations"),
        ("GET", "/api/v2/workspace-invitations"),
        ("POST", "/api/v2/workspace-invitations/{invitation_id}/accept"),
        ("POST", "/api/v2/workspace-invitations/{invitation_id}/reject"),
        ("POST", "/api/v2/workspace-invitations/{invitation_id}/cancel"),
        ("GET", "/api/v2/workspaces/{workspace_id}/lifecycle"),
        ("POST", "/api/v2/workspaces/{workspace_id}/transfer-ownership"),
        ("POST", "/api/v2/workspaces/{workspace_id}/deactivate"),
        ("POST", "/api/v2/workspaces/{workspace_id}/reactivate"),
        ("DELETE", "/api/v2/workspaces/{workspace_id}"),
        ("GET", "/api/v2/workspaces/{workspace_id}/categories"),
        ("POST", "/api/v2/workspaces/{workspace_id}/categories"),
        ("GET", "/api/v2/workspaces/{workspace_id}/categories/{category_id}"),
        ("PATCH", "/api/v2/workspaces/{workspace_id}/categories/{category_id}"),
        ("POST", "/api/v2/workspaces/{workspace_id}/categories/{category_id}/activate"),
        ("POST", "/api/v2/workspaces/{workspace_id}/categories/{category_id}/deactivate"),
        ("DELETE", "/api/v2/workspaces/{workspace_id}/categories/{category_id}"),
        ("GET", "/api/v2/workspaces/{workspace_id}/master-tasks"),
        ("POST", "/api/v2/workspaces/{workspace_id}/master-tasks"),
        ("GET", "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}"),
        ("PATCH", "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}"),
        ("POST", "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}/activate"),
        ("POST", "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}/deactivate"),
        ("DELETE", "/api/v2/workspaces/{workspace_id}/master-tasks/{item_id}"),
        ("GET", "/api/v2/workspaces/{workspace_id}/activity-masters"),
        ("POST", "/api/v2/workspaces/{workspace_id}/activity-masters"),
        ("GET", "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}"),
        ("PATCH", "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}"),
        ("POST", "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}/activate"),
        ("POST", "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}/deactivate"),
        ("DELETE", "/api/v2/workspaces/{workspace_id}/activity-masters/{item_id}"),
        ("GET", "/api/v2/workspaces/{workspace_id}/selectors/categories"),
        ("GET", "/api/v2/workspaces/{workspace_id}/selectors/tasks"),
            ("GET", "/api/v2/workspaces/{workspace_id}/selectors/activities"),
            ("GET", "/api/v2/workspaces/{workspace_id}/tasks"),
            ("POST", "/api/v2/workspaces/{workspace_id}/tasks"),
            ("GET", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}"),
            ("PATCH", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}"),
            ("DELETE", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}"),
            ("POST", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/complete"),
                ("POST", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/not-complete"),
                ("POST", "/api/v2/workspaces/{workspace_id}/tasks/{task_id}/correct-result"),
                ("POST", "/api/v2/workspaces/{workspace_id}/tasks/recurring"),
                ("GET", "/api/v2/workspaces/{workspace_id}/pending-items"),
                ("POST", "/api/v2/workspaces/{workspace_id}/pending-items"),
                ("GET", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}"),
                ("PATCH", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}"),
                ("DELETE", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}"),
                ("POST", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/progress"),
                ("POST", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/correction"),
                ("POST", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/deactivate"),
                ("POST", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/reactivate"),
                ("GET", "/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/history"),
                ("GET", "/api/v2/workspaces/{workspace_id}/projects"),
                ("POST", "/api/v2/workspaces/{workspace_id}/projects"),
                ("GET", "/api/v2/workspaces/{workspace_id}/projects/{project_id}"),
                ("PATCH", "/api/v2/workspaces/{workspace_id}/projects/{project_id}"),
                ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/deactivate"),
                ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/reactivate"),
                ("GET", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages"),
                    ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages"),
                    ("PUT", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/configuration"),
                    ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/reorder"),
                    ("GET", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}"),
                    ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/correction"),
                ("PATCH", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}"),
                ("GET", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/history"),
                ("POST", "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/progress"),
                ("GET", "/api/v2/workspaces/{workspace_id}/activities"),
                    ("POST", "/api/v2/workspaces/{workspace_id}/activities"),
                    ("POST", "/api/v2/workspaces/{workspace_id}/activities/recurring"),
                    ("GET", "/api/v2/workspaces/{workspace_id}/activities/{activity_id}"),
                ("PATCH", "/api/v2/workspaces/{workspace_id}/activities/{activity_id}"),
                ("DELETE", "/api/v2/workspaces/{workspace_id}/activities/{activity_id}"),
                ("POST", "/api/v2/workspaces/{workspace_id}/activities/{activity_id}/leave"),
        }
