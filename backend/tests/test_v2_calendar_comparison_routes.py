import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_usable_account
from app.main import app
from app.models import Activity, User, WorkspaceMember
from app.models.enums import CalendarVisibility
from app.services.v2_calendar import CalendarActivityProjection
from app.services.v2_calendar_comparison import BusyBlock, CalendarComparison, CalendarComparisonNotFoundError


def _client():
    account = User(id=uuid.uuid4(), email="viewer@example.test", first_name="Ana", last_name="Test")
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: account
    app.dependency_overrides[require_usable_account] = lambda: account
    return TestClient(app), db, account


def _params(target: uuid.UUID):
    return {"target_user_id": str(target), "from": "2027-01-04T05:00:00Z", "to": "2027-01-05T05:00:00Z"}


def test_comparison_contract_redacts_availability_and_hidden() -> None:
    client, db, _ = _client(); workspace_id, target = uuid.uuid4(), uuid.uuid4()
    start = datetime(2027, 1, 4, 15, tzinfo=timezone.utc)
    try:
        with patch("app.api.v2.calendar_comparison.compare_calendar", return_value=CalendarComparison(CalendarVisibility.AVAILABILITY_ONLY, [], [BusyBlock(start, start + timedelta(hours=2))])):
            response = client.get(f"/api/v2/workspaces/{workspace_id}/calendar-comparison", params=_params(target))
        assert response.status_code == 200
        assert response.json() == {"visibility": "AVAILABILITY_ONLY", "busy_blocks": [{"starts_at": "2027-01-04T15:00:00Z", "ends_at": "2027-01-04T17:00:00Z", "occupied": True}]}
        forbidden = ["activity_id", "title", "category", "workspace", "organizer", "participants", "generation_batch", "capabilities"]
        assert all(value not in response.text for value in forbidden)
        with patch("app.api.v2.calendar_comparison.compare_calendar", return_value=CalendarComparison(CalendarVisibility.HIDE, [], [])):
            hidden = client.get(f"/api/v2/workspaces/{workspace_id}/calendar-comparison", params=_params(target))
        assert hidden.json() == {"visibility": "HIDE"}
        db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_details_projection_has_no_origin_or_mutation_authority() -> None:
    client, _, _ = _client(); workspace_id, target = uuid.uuid4(), uuid.uuid4()
    start = datetime(2027, 1, 4, 15, tzinfo=timezone.utc)
    activity = Activity(id=uuid.uuid4(), workspace_id=uuid.uuid4(), organizer_user_id=target, title="Consulta privada", starts_at=start, ends_at=start + timedelta(hours=1))
    projection = CalendarActivityProjection(activity, MagicMock(), None, MagicMock(), MagicMock(), [], "FUTURE", True, True, True)
    try:
        with patch("app.api.v2.calendar_comparison.compare_calendar", return_value=CalendarComparison(CalendarVisibility.SHOW_DETAILS, [projection], [])):
            response = client.get(f"/api/v2/workspaces/{workspace_id}/calendar-comparison", params=_params(target))
        assert response.status_code == 200
        assert response.json() == {"visibility": "SHOW_DETAILS", "detailed_events": [{"activity_name": "Consulta privada", "starts_at": "2027-01-04T15:00:00Z", "ends_at": "2027-01-04T16:00:00Z", "temporal_state": "FUTURE"}]}
        assert "workspace" not in response.text and "can_edit" not in response.text and "activity_id" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_invalid_relationship_is_uniform_not_found() -> None:
    client, _, _ = _client(); workspace_id, target = uuid.uuid4(), uuid.uuid4()
    try:
        with patch("app.api.v2.calendar_comparison.compare_calendar", side_effect=CalendarComparisonNotFoundError):
            response = client.get(f"/api/v2/workspaces/{workspace_id}/calendar-comparison", params=_params(target))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CALENDAR_COMPARISON_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_visibility_update_commits_once_and_returns_authoritative_version() -> None:
    client, db, account = _client(); workspace_id = uuid.uuid4()
    membership = WorkspaceMember(workspace_id=workspace_id, user_id=account.id, calendar_visibility=CalendarVisibility.HIDE, lock_version=4)
    try:
        with patch("app.api.v2.calendar_comparison.update_calendar_visibility", return_value=membership) as update:
            response = client.patch(f"/api/v2/workspaces/{workspace_id}/calendar-visibility", json={"visibility": "HIDE", "lock_version": 4})
        assert response.status_code == 200 and response.json() == {"visibility": "HIDE", "lock_version": 4}
        update.assert_called_once(); db.commit.assert_called_once(); db.refresh.assert_called_once_with(membership)
    finally:
        app.dependency_overrides.clear()


def test_openapi_exposes_only_workspace_scoped_comparison_routes() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v2/workspaces/{workspace_id}/calendar-comparison" in paths
    assert "/api/v2/workspaces/{workspace_id}/calendar-visibility" in paths
    assert not any(path.startswith("/api/v2/calendar/{") for path in paths)
