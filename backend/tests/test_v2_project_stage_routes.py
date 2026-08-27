import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership, require_usable_account
from app.main import app
from app.models import Project, ProjectStage, User, Workspace, WorkspaceMember
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
    payload = {"responsible_user_id": str(USER_ID), "name": "Empacar", "position": 0, "weight": "100.00", "planned_date": "2026-09-10", "project_lock_version": 1}
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
