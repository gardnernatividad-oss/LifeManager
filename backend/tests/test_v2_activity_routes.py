import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import Activity, User, Workspace, WorkspaceMember
from app.models.enums import GlobalRole, WorkspaceKind
from app.schemas.v2_activity import ActivityRead
from app.services.v2_activity import ActivityConflictError, ActivityRecurrenceError
from app.services.v2_workspace import WorkspaceAccess


WORKSPACE_ID, ACTIVITY_ID, USER_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@pytest.fixture
def client():
    db = MagicMock(); user = User(id=USER_ID, email="ana@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=WORKSPACE_ID, name="Casa", kind=WorkspaceKind.SHARED, owner_user_id=USER_ID)
    access = WorkspaceAccess(workspace, WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    app.dependency_overrides[require_active_workspace_membership] = lambda: access
    try: yield TestClient(app), db, user, access
    finally: app.dependency_overrides.clear()


def payload():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    return {"activity_master_id": str(uuid.uuid4()), "organizer_user_id": str(USER_ID), "participant_user_ids": [str(USER_ID)], "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}


def read() -> ActivityRead:
    now = datetime.now(timezone.utc)
    return ActivityRead(id=ACTIVITY_ID, workspace_id=WORKSPACE_ID, activity_master_id=uuid.uuid4(), activity_master_name="Reunión", category_id=uuid.uuid4(), category_name="Familia", title="Reunión", organizer_user_id=USER_ID, organizer_display_name="Ana Uno", organizer_email="ana@test.local", participants=[], starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1), status="SCHEDULED", temporal_state="FUTURE", lock_version=1, is_generated=False, can_edit=True, can_delete=True, can_leave_participation=False, created_at=now, updated_at=now)


@patch("app.api.v2.activities._read", return_value=read())
@patch("app.api.v2.activities.create_activity", return_value=Activity())
def test_create_owns_transaction_and_passes_active_access(create, projection, client) -> None:
    http, db, user, access = client
    with patch.object(app, "openapi_schema", None):
        response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/activities", json=payload())
    assert response.status_code == 201
    assert create.call_args.kwargs["actor"] is user and create.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.refresh.assert_called_once(); db.rollback.assert_not_called()


@patch("app.api.v2.activities.update_activity", side_effect=ActivityConflictError())
def test_started_or_stale_activity_maps_to_409_and_rolls_back(update, client) -> None:
    http, db, *_ = client
    response = http.patch(f"/api/v2/workspaces/{WORKSPACE_ID}/activities/{ACTIVITY_ID}", json={"ends_at": "2026-09-01T15:00:00Z", "lock_version": 1})
    assert response.status_code == 409 and response.json()["error"]["code"] == "ACTIVITY_CONFLICT"
    db.rollback.assert_called_once(); db.commit.assert_not_called()


def test_activity_openapi_surface_and_mass_assignment(client) -> None:
    http, db, *_ = client
    body = payload() | {"workspace_id": str(WORKSPACE_ID), "generation_batch_id": str(uuid.uuid4()), "can_edit": True}
    assert http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/activities", json=body).status_code == 422
    paths = {path: set(methods) for path, methods in app.openapi()["paths"].items() if path.startswith("/api/v2/workspaces/{workspace_id}/activities")}
    assert paths == {
        "/api/v2/workspaces/{workspace_id}/activities": {"get", "post"},
        "/api/v2/workspaces/{workspace_id}/activities/recurring": {"post"},
        "/api/v2/workspaces/{workspace_id}/activities/{activity_id}": {"get", "patch", "delete"},
        "/api/v2/workspaces/{workspace_id}/activities/{activity_id}/leave": {"post"},
    }
    db.commit.assert_not_called()


@patch("app.api.v2.activities._read", return_value=read())
@patch("app.api.v2.activities.create_recurring_activities", return_value=[Activity()])
def test_recurring_create_is_atomic_router_write(create, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/activities/recurring", json={
        "activity_master_id": str(uuid.uuid4()), "organizer_user_id": str(USER_ID),
        "participant_user_ids": [str(USER_ID)], "start_time": "09:00", "end_time": "10:00",
        "timezone": "America/Lima", "recurrence": {"pattern": "DAILY", "date_from": "2027-01-01", "date_until": "2027-01-02"},
    })
    assert response.status_code == 201 and response.json()["created_count"] == 1
    assert create.call_args.kwargs["actor"] is user and create.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.rollback.assert_not_called()


@patch("app.api.v2.activities.create_recurring_activities", side_effect=ActivityRecurrenceError())
def test_invalid_recurring_local_time_maps_to_422_and_rolls_back(create, client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/activities/recurring", json={
        "activity_master_id": str(uuid.uuid4()), "organizer_user_id": str(USER_ID),
        "participant_user_ids": [], "start_time": "02:30", "end_time": "03:30",
        "timezone": "America/New_York", "recurrence": {"pattern": "DAILY", "date_from": "2027-03-14", "date_until": "2027-03-14"},
    })
    assert response.status_code == 422 and response.json()["error"]["code"] == "ACTIVITY_RECURRENCE_INVALID"
    db.rollback.assert_called_once(); db.commit.assert_not_called()


def test_anonymous_and_global_admin_nonmember_have_no_activity_access() -> None:
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as http:
            assert http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/activities").status_code == 401
        db = MagicMock(); account = User(id=uuid.uuid4(), email="admin@test.local", global_role=GlobalRole.GLOBAL_ADMIN)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_account] = lambda: account
        app.dependency_overrides[require_usable_account] = lambda: account
        with TestClient(app) as http:
            response = http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/activities")
        assert response.status_code == 404 and response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
