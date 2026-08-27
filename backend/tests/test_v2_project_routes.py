import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import Project, User, Workspace, WorkspaceMember
from app.models.enums import GlobalRole, WorkspaceKind
from app.schemas.v2_project import ProjectRead
from app.services.v2_project import ProjectConflictError
from app.services.v2_workspace import WorkspaceAccess


WORKSPACE_ID, PROJECT_ID, USER_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def read() -> ProjectRead:
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return ProjectRead(id=PROJECT_ID, workspace_id=WORKSPACE_ID, category_id=uuid.uuid4(), category_name="Casa", leader_user_id=USER_ID, leader_display_name="Ana Uno", leader_email="ana@test.local", name="Mudanza", description=None, is_active=True, planned_date=None, progress=0, state="NO_INICIADO", compliance=None, compliance_detail_days=None, completion_date=None, weights_complete=False, stage_count=0, total_weight=0, lock_version=1, can_edit=True, can_deactivate=True, can_reactivate=False, created_at=now, updated_at=now)


@pytest.fixture
def client():
    db = MagicMock(); user = User(id=USER_ID, email="ana@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=WORKSPACE_ID, name="Casa", kind=WorkspaceKind.SHARED, owner_user_id=USER_ID)
    access = WorkspaceAccess(workspace, WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    app.dependency_overrides[require_active_workspace_membership] = lambda: access
    try:
        yield TestClient(app), db, user, access
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v2.projects._read", return_value=read())
@patch("app.api.v2.projects.create_project", return_value=Project())
def test_create_uses_active_member_and_route_owns_transaction(create, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects", json={"category_id": str(uuid.uuid4()), "leader_user_id": str(USER_ID), "name": "Mudanza"})
    assert response.status_code == 201 and response.json()["progress"] == 0.0
    assert create.call_args.kwargs["actor"] is user and create.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.refresh.assert_called_once(); db.rollback.assert_not_called()


@patch("app.api.v2.projects._read", return_value=read())
@patch("app.api.v2.projects.list_projects", return_value=([(Project(), MagicMock(), MagicMock())], 1))
def test_list_is_scoped_filtered_and_read_only(listing, projection, client) -> None:
    http, db, *_ = client
    response = http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/projects", params={"is_active": "true", "category_id": str(uuid.uuid4()), "leader_user_id": str(USER_ID), "search": " muda ", "page_size": 50})
    assert response.status_code == 200 and response.json()["total"] == 1
    assert listing.call_args.kwargs["workspace_id"] == WORKSPACE_ID and listing.call_args.kwargs["search"] == "muda"
    db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()


@patch("app.api.v2.projects.update_project", side_effect=ProjectConflictError())
def test_conflict_rolls_back(update, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}", json={"name": "Otro", "lock_version": 1})
    assert response.status_code == 409 and response.json()["error"]["code"] == "PROJECT_CONFLICT"
    db.rollback.assert_called_once(); db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("path", "service_name"),
    (("deactivate", "deactivate_project"), ("reactivate", "reactivate_project")),
)
def test_lifecycle_routes_keep_account_timezone_for_response(path, service_name, client) -> None:
    http, db, _, _ = client
    with patch(f"app.api.v2.projects.{service_name}", return_value=Project()), patch("app.api.v2.projects.local_today", return_value=date(2026, 9, 1)), patch("app.api.v2.projects._read", return_value=read()) as projection:
        response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/{path}", json={"lock_version": 1})
    assert response.status_code == 200
    assert projection.call_args.kwargs["today"] == date(2026, 9, 1)
    db.commit.assert_called_once(); db.refresh.assert_called_once(); db.rollback.assert_not_called()


def test_mass_assignment_and_openapi_surface(client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects", json={"category_id": str(uuid.uuid4()), "name": "X", "workspace_id": str(WORKSPACE_ID), "progress": 100, "can_edit": True, "stages": []})
    assert response.status_code == 422 and not db.commit.called
    paths = {path: set(methods) for path, methods in app.openapi()["paths"].items() if path.startswith("/api/v2/workspaces/{workspace_id}/projects")}
    assert paths == {
        "/api/v2/workspaces/{workspace_id}/projects": {"get", "post"},
        "/api/v2/workspaces/{workspace_id}/projects/{project_id}": {"get", "patch"},
        "/api/v2/workspaces/{workspace_id}/projects/{project_id}/deactivate": {"post"},
        "/api/v2/workspaces/{workspace_id}/projects/{project_id}/reactivate": {"post"},
        "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages": {"get", "post"},
            "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}": {"get", "patch"},
            "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/history": {"get"},
            "/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/progress": {"post"},
    }


def test_anonymous_and_global_admin_nonmember_cannot_access_projects() -> None:
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as http:
            assert http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/projects").status_code == 401

        for role in (None, GlobalRole.GLOBAL_ADMIN):
            db = MagicMock(); db.execute.return_value.one_or_none.return_value = None
            account = User(id=uuid.uuid4(), email="outsider@test.local", global_role=role)
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_account] = lambda: account
            app.dependency_overrides[require_usable_account] = lambda: account
            with TestClient(app) as http:
                response = http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/projects")
            assert response.status_code == 404 and response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
