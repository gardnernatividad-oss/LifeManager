import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import User, Workspace, WorkspaceKind
from app.schemas.home import HomeSummary


def test_home_uses_authenticated_context_timezone_and_is_read_only() -> None:
    db = MagicMock(spec=Session)
    user = User(
        id=uuid.uuid4(), first_name="Ana", last_name="Pérez",
        timezone="Pacific/Kiritimati", is_active=True,
    )
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    summary = HomeSummary(
        user_first_name="Ana", local_date=date(2026, 8, 13),
        tasks={"due_today": 1, "overdue": 2},
        pending_items={"overdue": 3}, project_steps={"overdue": 4},
        last_review_saved_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        pending_items_last_tracking_saved_at=None,
    )
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.home.local_today", return_value=date(2026, 8, 13)
        ) as today, patch(
            "app.api.v1.home.home_service.get_home_summary", return_value=summary
        ) as service:
            response = client.get("/api/v1/home")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "user_first_name": "Ana", "local_date": "2026-08-13",
        "tasks": {"due_today": 1, "overdue": 2},
        "pending_items": {"overdue": 3}, "project_steps": {"overdue": 4},
        "last_review_saved_at": "2026-08-12T00:00:00Z",
        "pending_items_last_tracking_saved_at": None,
    }
    today.assert_called_once_with("Pacific/Kiritimati")
    assert service.call_args.args == (db,)
    assert service.call_args.kwargs == {
        "workspace_id": workspace.id,
        "user_first_name": "Ana", "local_date": date(2026, 8, 13),
    }
    db.add.assert_not_called(); db.flush.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_home_requires_authentication_and_has_no_legacy_dashboard_fields() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/home")
    assert response.status_code == 401
    schema = HomeSummary.model_json_schema()
    fields = set(schema["properties"])
    assert not fields.intersection({
        "completion_rate", "scheduled_tasks", "completed_tasks",
        "cancelled_tasks", "total_tasks", "navigate_to", "module_url", "actions",
    })
