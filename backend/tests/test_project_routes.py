import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import Category, Project, ProjectStep, User, Workspace, WorkspaceKind
from app.services.project_service import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectVersionConflictError,
)


@pytest.fixture
def project_routes():
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client:
        yield client, db, user, workspace
    app.dependency_overrides.clear()


def _project(workspace_id, user_id):
    timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Personal",
        normalized_name="personal", created_at=timestamp, updated_at=timestamp,
    )
    project = Project(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Mudanza", is_active=True,
        general_comment="Actual", last_tracking_saved_at=timestamp,
        created_by_id=user_id, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )
    step = ProjectStep(
        id=uuid.uuid4(), project_id=project.id, project=project, name="Empacar",
        planned_date=date(2026, 8, 12), weight=Decimal("100"), progress=0,
        completion_date=None, comment=None, position=0, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )
    project.steps = [step]
    return project


def test_create_commits_context_and_serializes_detail(project_routes) -> None:
    client, db, user, workspace = project_routes
    project = _project(workspace.id, user.id)
    with patch(
        "app.api.v1.projects.project_service.create_project", return_value=project
    ) as service:
        response = client.post("/api/v1/projects", json={
            "category_id": str(project.category_id), "name": "Mudanza",
            "is_active": True, "steps": [{"name": "Empacar",
                "planned_date": "2026-08-12", "weight": "100", "position": 0}],
        })
    assert response.status_code == 201
    assert response.json()["progress"] == "0" and len(response.json()["steps"]) == 1
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["current_user"] is user
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(project)


def test_list_filters_paginates_and_is_read_only(project_routes) -> None:
    client, db, user, workspace = project_routes
    project = _project(workspace.id, user.id)
    with patch(
        "app.api.v1.projects.project_service.list_projects", return_value=([project], 26)
    ) as service:
        response = client.get(
            f"/api/v1/projects?page=2&page_size=25&is_active=true"
            f"&category_id={project.category_id}&state=NO_INICIADO"
            "&planned_from=2026-08-01&planned_to=2026-08-31"
        )
    assert response.status_code == 200 and response.json()["total_pages"] == 2
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_detail_and_planning_step_routes(project_routes) -> None:
    client, db, user, workspace = project_routes
    project = _project(workspace.id, user.id); step = project.steps[0]
    with patch("app.api.v1.projects.project_service.get_project", return_value=project):
        response = client.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 200 and response.json()["steps"][0]["name"] == "Empacar"

    with patch("app.api.v1.projects.project_service.create_project_step", return_value=step):
        response = client.post(f"/api/v1/projects/{project.id}/steps", json={
            "name": "Empacar", "planned_date": "2026-08-12",
            "weight": "100", "position": 0,
        })
    assert response.status_code == 201
    with patch("app.api.v1.projects.project_service.update_project_step", return_value=step):
        response = client.patch(
            f"/api/v1/projects/{project.id}/steps/{step.id}",
            json={"name": "Empacar cajas", "lock_version": 1},
        )
    assert response.status_code == 200


def test_general_comment_commit_does_not_use_detail_tracking(project_routes) -> None:
    client, db, user, workspace = project_routes
    project = _project(workspace.id, user.id)
    with patch(
        "app.api.v1.projects.project_service.update_project_general_tracking",
        return_value=project,
    ) as service:
        response = client.patch(
            f"/api/v1/projects/{project.id}/tracking-general",
            json={"general_comment": "Actualizado", "lock_version": 1},
        )
    assert response.status_code == 200
    assert service.call_args.kwargs["project_in"].general_comment == "Actualizado"
    db.commit.assert_called_once_with()
    response = client.patch(
        f"/api/v1/projects/{project.id}/tracking-general",
        json={"is_active": False, "lock_version": 1},
    )
    assert response.status_code == 422


def test_tracking_batch_commits_once_and_returns_timestamp(project_routes) -> None:
    client, db, user, workspace = project_routes
    project = _project(workspace.id, user.id); saved = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    with patch(
        "app.api.v1.projects.project_service.save_project_tracking",
        return_value=(project, saved),
    ):
        response = client.patch(f"/api/v1/projects/{project.id}/tracking", json={
            "project_lock_version": 1,
            "items": [{"id": str(project.steps[0].id), "progress": 50, "lock_version": 1}],
        })
    assert response.status_code == 200
    assert response.json()["saved_at"] == "2026-08-12T20:00:00Z"
    db.commit.assert_called_once_with()
    assert db.refresh.call_count == 2


def test_inactive_project_tracking_maps_to_conflict_and_rolls_back(project_routes) -> None:
    client, db, _user, _workspace = project_routes
    with patch(
        "app.api.v1.projects.project_service.save_project_tracking",
        side_effect=ProjectConflictError("Inactive Projects cannot be tracked"),
    ):
        response = client.patch(f"/api/v1/projects/{uuid.uuid4()}/tracking", json={
            "project_lock_version": 1,
            "items": [{"id": str(uuid.uuid4()), "progress": 50, "lock_version": 1}],
        })
    assert response.status_code == 409
    assert response.json()["detail"] == "Inactive Projects cannot be tracked"
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code"),
    [(ProjectNotFoundError("Project not found"), 404),
     (ProjectConflictError("Invalid structure"), 409),
     (ProjectVersionConflictError("Project version is stale"), 409)],
)
def test_domain_write_errors_rollback(project_routes, error, code) -> None:
    client, db, _user, _workspace = project_routes
    with patch(
        "app.api.v1.projects.project_service.save_project_tracking", side_effect=error
    ):
        response = client.patch(f"/api/v1/projects/{uuid.uuid4()}/tracking", json={
            "project_lock_version": 1,
            "items": [{"id": str(uuid.uuid4()), "progress": 50, "lock_version": 1}],
        })
    assert response.status_code == code
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_boundaries_auth_and_no_delete_route(project_routes) -> None:
    client, db, _user, _workspace = project_routes
    project_id = uuid.uuid4(); step_id = uuid.uuid4()
    response = client.patch(f"/api/v1/projects/{project_id}/steps/{step_id}", json={
        "progress": 50, "lock_version": 1,
    })
    assert response.status_code == 422
    response = client.patch(f"/api/v1/projects/{project_id}/tracking", json={
        "project_lock_version": 1,
        "items": [{"id": str(step_id), "planned_date": "2026-08-12", "lock_version": 1}],
    })
    assert response.status_code == 422
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 405

    app.dependency_overrides.clear()
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/projects").status_code == 401
