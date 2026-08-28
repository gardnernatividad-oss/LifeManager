import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import Project, ProjectStage, ProjectStageHistory, User, Workspace, WorkspaceMember
from app.models.enums import HistoryEventType
from app.models.enums import WorkspaceKind
from app.schemas.v2_project_stage import ProjectStageRead
from app.services.v2_project_stage import ProjectStageConflictError
from app.services.v2_workspace import WorkspaceAccess


WORKSPACE_ID, PROJECT_ID, STAGE_ID, USER_ID = (uuid.uuid4() for _ in range(4))


def stage_read() -> ProjectStageRead:
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return ProjectStageRead(id=STAGE_ID, workspace_id=WORKSPACE_ID, project_id=PROJECT_ID, responsible_user_id=USER_ID, responsible_display_name="Ana Uno", responsible_email="ana@test.local", name="Empacar", position=0, weight=Decimal("100"), planned_date=date(2026, 9, 10), progress=0, state="NO_INICIADA", completion_date=None, compliance="EN_PLAZO", compliance_detail_days=9, lock_version=1, can_edit=True, can_update_progress=True, created_at=now, updated_at=now)


@pytest.fixture
def client():
    db = MagicMock(); user = User(id=USER_ID, email="ana@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=WORKSPACE_ID, name="Casa", kind=WorkspaceKind.SHARED, owner_user_id=USER_ID)
    access = WorkspaceAccess(workspace, WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID))
    app.dependency_overrides[get_db] = lambda: db; app.dependency_overrides[get_current_account] = lambda: user; app.dependency_overrides[require_usable_account] = lambda: user; app.dependency_overrides[require_active_workspace_membership] = lambda: access
    try:
        yield TestClient(app), db, user, access
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v2.project_stages._read", return_value=stage_read())
@patch("app.api.v2.project_stages.create_project_stage", return_value=ProjectStage())
def test_create_is_scoped_strict_and_route_owns_transaction(create, projection, client) -> None:
    http, db, user, access = client
    payload = {"responsible_user_id": str(USER_ID), "name": "Empacar", "weight": "100.00", "planned_date": "2026-09-10", "project_lock_version": 1}
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages", json=payload)
    assert response.status_code == 201 and response.json()["state"] == "NO_INICIADA"
    assert create.call_args.kwargs["access"] is access and create.call_args.kwargs["actor"] is user
    db.commit.assert_called_once(); db.refresh.assert_called_once(); db.rollback.assert_not_called()
    invalid = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages", json={**payload, "workspace_id": str(WORKSPACE_ID), "completion_date": "2026-09-10"})
    assert invalid.status_code == 422


@patch("app.api.v2.project_stages.update_project_stage_progress", side_effect=ProjectStageConflictError())
def test_progress_conflict_rolls_back(update, client) -> None:
    http, db, *_ = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/progress", json={"progress": 50, "lock_version": 1, "project_lock_version": 1})
    assert response.status_code == 409 and db.rollback.call_count == 1 and not db.commit.called


@patch("app.api.v2.project_stages._read", return_value=stage_read())
@patch("app.api.v2.project_stages.update_project_stage_progress", return_value=ProjectStage())
def test_progress_accepts_one_atomic_comment_and_rejects_mass_assignment(update, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/progress", json={"progress": 50, "comment": "Avance real", "lock_version": 1, "project_lock_version": 1})
    assert response.status_code == 200
    assert update.call_args.kwargs["actor"] is user and update.call_args.kwargs["comment"] == "Avance real"
    db.commit.assert_called_once()
    invalid = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/progress", json={"comment": "x", "actor_user_id": str(USER_ID), "workspace_id": str(WORKSPACE_ID), "lock_version": 1, "project_lock_version": 1})
    assert invalid.status_code == 422


@patch("app.api.v2.project_stages.list_project_stage_history")
def test_history_is_hierarchically_scoped_and_read_only(history, client) -> None:
    http, db, *_ = client
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    history.return_value = [(ProjectStageHistory(id=uuid.uuid4(), project_stage_id=STAGE_ID, workspace_id=WORKSPACE_ID, actor_user_id=USER_ID, progress=50, comment="Mitad", event_type=HistoryEventType.TRACKING, recorded_at=now), User(id=USER_ID, first_name="Ana", last_name="Uno"))]
    response = http.get(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/history")
    assert response.status_code == 200 and response.json()["items"][0]["comment"] == "Mitad"
    assert history.call_args.args == (db,) and history.call_args.kwargs == {"workspace_id": WORKSPACE_ID, "project_id": PROJECT_ID, "stage_id": STAGE_ID}
    assert not db.commit.called and not db.flush.called and not db.rollback.called
    assert http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/history", json={}).status_code == 405


@patch("app.api.v2.project_stages._list_read", return_value={"items": [], "total_weight": "0.00", "weights_complete": False})
@patch("app.api.v2.project_stages.configure_project_stages", return_value=[])
def test_configuration_is_atomic_and_position_is_not_client_controlled(configure, projection, client) -> None:
    http, db, user, access = client
    response = http.put(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/configuration", json={"items": [{"name": "Etapa", "responsible_user_id": str(USER_ID), "weight": "100.00", "planned_date": "2026-09-10"}], "project_lock_version": 1})
    assert response.status_code == 200
    assert configure.call_args.kwargs["actor"] is user and configure.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.rollback.assert_not_called()
    invalid = http.put(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/configuration", json={"items": [{"name": "Etapa", "weight": "99.99", "planned_date": "2026-09-10", "position": 9}], "project_lock_version": 1})
    assert invalid.status_code == 422


@patch("app.api.v2.project_stages._read", return_value=stage_read())
@patch("app.api.v2.project_stages.correct_project_stage_progress", return_value=ProjectStage())
def test_explicit_correction_commits_once(correction, projection, client) -> None:
    http, db, user, access = client
    response = http.post(f"/api/v2/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/stages/{STAGE_ID}/correction", json={"progress": "80.25", "comment": "Corrección", "lock_version": 1, "project_lock_version": 2})
    assert response.status_code == 200
    assert correction.call_args.kwargs["progress"] == Decimal("80.25") and correction.call_args.kwargs["actor"] is user and correction.call_args.kwargs["access"] is access
    db.commit.assert_called_once(); db.refresh.assert_called_once()
