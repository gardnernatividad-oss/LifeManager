import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_usable_account
from app.main import app
from app.models import Activity, ActivityMaster, Category, User, Workspace, WorkspaceMember
from app.models.enums import ActivityStatus, WorkspaceKind
from app.services.v2_calendar import CalendarActivityProjection


def test_calendar_me_is_authenticated_global_and_serializes_safe_projection() -> None:
    user_id, workspace_id, activity_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = User(id=user_id, email="ana@test.local", first_name="Ana", last_name="Uno")
    workspace = Workspace(id=workspace_id, name="Familia", kind=WorkspaceKind.SHARED, owner_user_id=user_id)
    master = ActivityMaster(id=uuid.uuid4(), workspace_id=workspace_id, category_id=uuid.uuid4(), name="Reunión", normalized_name="reunión")
    category = Category(id=master.category_id, workspace_id=workspace_id, name="Familia", normalized_name="familia")
    start = datetime(2027, 1, 4, 15, tzinfo=timezone.utc)
    activity = Activity(id=activity_id, workspace_id=workspace_id, organizer_user_id=user_id, activity_master_id=master.id, title=master.name, starts_at=start, ends_at=start + timedelta(hours=1), status=ActivityStatus.SCHEDULED, lock_version=2)
    projection = CalendarActivityProjection(activity, workspace, master, category, user, [user], "FUTURE", True, True, True)
    db = MagicMock(); app.dependency_overrides[get_db] = lambda: db; app.dependency_overrides[get_current_account] = lambda: user; app.dependency_overrides[require_usable_account] = lambda: user
    try:
        with patch("app.api.v2.calendar.list_my_calendar", return_value=[projection]) as listing:
            response = TestClient(app).get("/api/v2/calendar/me", params={"from": "2027-01-04T05:00:00Z", "to": "2027-01-11T05:00:00Z"})
        assert response.status_code == 200 and response.json()["items"][0]["workspace"]["name"] == "Familia"
        assert listing.call_args.kwargs["user_id"] == user_id
        assert "generation_batch_id" not in response.text and "membership" not in response.text
        db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_calendar_me_rejects_missing_auth_and_invalid_ranges() -> None:
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/v2/calendar/me", params={"from": "2027-01-01T00:00:00Z", "to": "2027-01-02T00:00:00Z"}).status_code == 401
