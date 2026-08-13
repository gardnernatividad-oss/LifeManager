import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import Category, MasterTask, PendingItem, Project, ProjectStep, Task, User, Workspace, WorkspaceKind
from app.services.review_service import ReviewConflictError, ReviewNotFoundError, ReviewVersionConflictError


@pytest.fixture
def review_routes():
    db = MagicMock(spec=Session); user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client: yield client, db, user, workspace
    app.dependency_overrides.clear()


def _rows(workspace_id):
    now = datetime.now(timezone.utc)
    category = Category(id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud")
    master = MasterTask(id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id, name="Correr", normalized_name="correr")
    task = Task(id=uuid.uuid4(), workspace_id=workspace_id, master_task_id=master.id, master_task=master, planned_date=date(2026, 8, 11), lock_version=1, created_at=now, updated_at=now)
    pending = PendingItem(id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id, name="Control", is_active=True, planned_date=date(2026, 8, 12), progress=20, lock_version=1, created_at=now, updated_at=now)
    project = Project(id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id, name="Mudanza", is_active=True, lock_version=1, created_at=now, updated_at=now)
    step = ProjectStep(id=uuid.uuid4(), project_id=project.id, project=project, name="Empacar", planned_date=date(2026, 8, 10), weight=Decimal("100"), progress=30, position=0, lock_version=1, created_at=now, updated_at=now)
    project.steps = [step]
    return task, pending, step


def test_get_review_is_compact_grouped_local_and_read_only(review_routes) -> None:
    client, db, _user, workspace = review_routes; task, pending, step = _rows(workspace.id)
    saved = datetime(2026, 8, 11, tzinfo=timezone.utc)
    with patch("app.api.v1.review.local_today", return_value=date(2026, 8, 12)), patch(
        "app.api.v1.review.review_service.get_review", return_value=([task], [pending], [step], saved)
    ):
        response = client.get("/api/v1/review")
    assert response.status_code == 200
    payload = response.json(); assert payload["review_date"] == "2026-08-12"
    assert set(payload["tasks"][0]) == {"id", "planned_date", "name", "lock_version"}
    assert set(payload["pending_items"][0]) == {"id", "planned_date", "name", "progress", "comment", "lock_version"}
    assert payload["projects"][0]["name"] == "Mudanza" and len(payload["projects"][0]["steps"]) == 1
    assert "general_comment" not in payload["projects"][0]
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_review_save_commits_once_and_allows_empty(review_routes) -> None:
    client, db, user, workspace = review_routes
    saved = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    with patch("app.api.v1.review.review_service.save_review", return_value=saved) as service:
        response = client.patch("/api/v1/review", json={})
    assert response.status_code == 200 and response.json()["saved_at"] == "2026-08-12T20:00:00Z"
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["current_user"] is user
    db.commit.assert_called_once_with(); db.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code"),
    [(ReviewNotFoundError("Review item not found"), 404),
     (ReviewConflictError("Not eligible"), 409),
     (ReviewVersionConflictError("Stale"), 409)],
)
def test_review_save_errors_rollback(review_routes, error, code) -> None:
    client, db, _user, _workspace = review_routes
    with patch("app.api.v1.review.review_service.save_review", side_effect=error):
        response = client.patch("/api/v1/review", json={})
    assert response.status_code == code
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


@pytest.mark.parametrize("section, extra", [
    ("tasks", {"planned_date": "2026-08-12"}),
    ("pending_items", {"is_active": False}),
    ("project_steps", {"weight": "50"}),
])
def test_review_save_rejects_cross_boundary_fields(review_routes, section, extra) -> None:
    client, db, _user, _workspace = review_routes
    row = {"id": str(uuid.uuid4()), "lock_version": 1, **extra}
    if section == "tasks": row["result"] = "COMPLETED"
    elif section == "pending_items": row["progress"] = 50
    else: row["progress"] = 50
    response = client.patch("/api/v1/review", json={section: [row]})
    assert response.status_code == 422 and not db.commit.called


def test_review_requires_authentication() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/review").status_code == 401
