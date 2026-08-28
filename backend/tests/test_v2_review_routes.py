import uuid

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_usable_account
from app.main import app
from app.models import MasterTask, PendingItem, Project, ProjectStage, Task, User, Workspace
from app.services.v2_review import GlobalReviewSelection


def test_review_is_global_authenticated_serialized_and_read_only() -> None:
    user = User(id=uuid.uuid4(), email="ana@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=user.id, name="Familia")
    master = MasterTask(id=uuid.uuid4(), workspace_id=workspace.id, category_id=uuid.uuid4(), name="Comprar", normalized_name="comprar")
    task = Task(id=uuid.uuid4(), workspace_id=workspace.id, master_task_id=master.id, responsible_user_id=user.id, planned_date=date(2026, 8, 28), lock_version=2)
    pending = PendingItem(id=uuid.uuid4(), workspace_id=workspace.id, category_id=master.category_id, responsible_user_id=user.id, name="Mudanza", planned_date=date(2026, 8, 27), progress=40, lock_version=3)
    project = Project(id=uuid.uuid4(), workspace_id=workspace.id, category_id=master.category_id, leader_user_id=user.id, name="Casa")
    stage = ProjectStage(id=uuid.uuid4(), workspace_id=workspace.id, project_id=project.id, responsible_user_id=user.id, name="Cotizar", position=0, weight=100, planned_date=date(2026, 8, 26), progress=20, lock_version=4)
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    selection = GlobalReviewSelection(tasks=[(task, master, workspace)], pending_items=[(pending, workspace)], project_stages=[(stage, project, workspace)])
    try:
        with patch("app.api.v2.review.local_today", return_value=date(2026, 8, 28)), patch("app.api.v2.review.get_global_review", return_value=selection) as service:
            response = TestClient(app).get("/api/v2/review")
        assert response.status_code == 200
        body = response.json()
        assert body["review_date"] == "2026-08-28"
        assert body["tasks"][0]["task_name"] == "Comprar"
        assert body["pending_items"][0]["progress"] == 40
        assert body["project_stages"][0]["project_name"] == "Casa"
        assert all(item["workspace_name"] == "Familia" for item in (body["tasks"][0], body["pending_items"][0], body["project_stages"][0]))
        assert service.call_args.kwargs == {"user_id": user.id, "local_date": date(2026, 8, 28)}
        db.add.assert_not_called(); db.delete.assert_not_called(); db.flush.assert_not_called()
        db.commit.assert_not_called(); db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_review_requires_authentication_and_has_no_workspace_parameter() -> None:
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v2/review")
    assert response.status_code == 401
    operation = app.openapi()["paths"]["/api/v2/review"]["get"]
    assert all(parameter["name"] != "workspace_id" for parameter in operation.get("parameters", []))
