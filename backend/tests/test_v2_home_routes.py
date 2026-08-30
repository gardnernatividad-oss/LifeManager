import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_usable_account
from app.main import app
from app.models import Activity, ActivityMaster, Category, User, Workspace
from app.models.enums import WorkspaceColor, WorkspaceIcon
from app.services.v2_calendar import CalendarActivityProjection
from app.services.v2_home import HomeAttentionProjection, HomeSummaryProjection


def test_home_is_global_authenticated_compact_and_read_only() -> None:
    user = User(id=uuid.uuid4(), email="ana@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=user.id, name="Familia", color=WorkspaceColor.PURPLE, icon=WorkspaceIcon.USERS)
    master = ActivityMaster(id=uuid.uuid4(), workspace_id=workspace.id, category_id=uuid.uuid4(), name="Cena", normalized_name="cena")
    activity = Activity(id=uuid.uuid4(), workspace_id=workspace.id, activity_master_id=master.id, organizer_user_id=user.id, starts_at=datetime(2026, 8, 31, 0, tzinfo=timezone.utc), ends_at=datetime(2026, 8, 31, 1, tzinfo=timezone.utc))
    projection = CalendarActivityProjection(activity, workspace, master, Category(id=master.category_id, workspace_id=workspace.id, name="Familia", normalized_name="familia"), user, [user], "FUTURE", True, True, False)
    result = HomeSummaryProjection(date(2026, 8, 30), (1, 2, 3, 4), [projection], [HomeAttentionProjection("TASK", uuid.uuid4(), workspace, "Comprar", date(2026, 8, 29))], [(date(2026, 8, 31), 1, 0, 2, 1)])
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    try:
        with patch("app.api.v2.home.get_home_summary", return_value=result) as service:
            response = TestClient(app).get("/api/v2/home")
        assert response.status_code == 200
        body = response.json()
        assert body["today"] == {"tasks": 1, "pending_items": 2, "project_stages": 3, "activities": 4}
        assert body["upcoming_activities"][0]["name"] == "Cena"
        assert body["upcoming_activities"][0]["workspace"]["color"] == "PURPLE"
        assert body["attention"][0]["type"] == "TASK"
        assert body["upcoming_days"][0]["date"] == "2026-08-31"
        assert service.call_args.kwargs["user_id"] == user.id
        assert service.call_args.kwargs["timezone_name"] == "America/Lima"
        db.add.assert_not_called(); db.flush.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_home_requires_authentication_and_has_no_workspace_parameter() -> None:
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/v2/home").status_code == 401
    operation = app.openapi()["paths"]["/api/v2/home"]["get"]
    assert all(parameter["name"] != "workspace_id" for parameter in operation.get("parameters", []))
