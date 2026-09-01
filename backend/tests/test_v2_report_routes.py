import uuid

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import (
    get_current_account,
    get_db,
    require_active_workspace_membership,
    require_usable_account,
)
from app.main import app
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import GlobalRole
from app.services.v2_report import ReportSummaryProjection
from app.services.v2_workspace import WorkspaceAccess


def _client():
    user = User(id=uuid.uuid4(), email="ana@example.test", first_name="Ana", last_name="Uno", timezone="America/Lima")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=user.id, name="Personal")
    access = WorkspaceAccess(workspace, WorkspaceMember(workspace_id=workspace.id, user_id=user.id))
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    app.dependency_overrides[require_active_workspace_membership] = lambda: access
    return TestClient(app), user, workspace, db


def test_report_summary_is_workspace_scoped_serialized_and_read_only() -> None:
    client, user, workspace, db = _client()
    category_id = uuid.uuid4()
    responsible_id = uuid.uuid4()
    try:
        with (
            patch("app.api.v2.reports.local_today", return_value=date(2026, 8, 30)),
            patch("app.api.v2.reports.get_report_summary", return_value=ReportSummaryProjection(4, 3, 2, 1)) as service,
        ):
            response = client.get(
                f"/api/v2/workspaces/{workspace.id}/reports/summary",
                params={
                    "date_from": "2026-08-01",
                    "date_until": "2026-08-31",
                    "category_id": str(category_id),
                    "responsible_user_id": str(responsible_id),
                },
            )
        assert response.status_code == 200
        assert response.json() == {
            "local_date": "2026-08-30",
            "date_from": "2026-08-01",
            "date_until": "2026-08-31",
            "category_id": str(category_id),
            "responsible_user_id": str(responsible_id),
            "counts": {"tasks": 4, "pending_items": 3, "projects": 2, "activities": 1, "total": 10},
        }
        assert service.call_args.kwargs == {
            "workspace_id": workspace.id,
            "timezone_name": user.timezone,
            "date_from": date(2026, 8, 1),
            "date_until": date(2026, 8, 31),
            "category_id": category_id,
            "responsible_user_id": responsible_id,
        }
        db.add.assert_not_called()
        db.flush.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_report_summary_rejects_reversed_range_before_query() -> None:
    client, _user, workspace, _db = _client()
    try:
        with patch("app.api.v2.reports.get_report_summary") as service:
            response = client.get(
                f"/api/v2/workspaces/{workspace.id}/reports/summary",
                params={"date_from": "2026-09-01", "date_until": "2026-08-31"},
            )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"
        service.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_report_summary_requires_authentication_and_valid_uuids() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)
    assert client.get(f"/api/v2/workspaces/{uuid.uuid4()}/reports/summary").status_code == 401
    assert client.get("/api/v2/workspaces/not-a-uuid/reports/summary").status_code in {401, 422}


def test_report_summary_requires_active_membership_without_global_admin_bypass() -> None:
    user = User(
        id=uuid.uuid4(), email="admin@example.test", first_name="Admin", last_name="Uno",
        timezone="America/Lima", global_role=GlobalRole.GLOBAL_ADMIN,
    )
    db = MagicMock()
    db.execute.return_value.one_or_none.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: user
    app.dependency_overrides[require_usable_account] = lambda: user
    try:
        with patch("app.api.v2.reports.get_report_summary") as service:
            response = TestClient(app).get(f"/api/v2/workspaces/{uuid.uuid4()}/reports/summary")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
        service.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_report_summary_openapi_contract_is_minimal_and_read_only() -> None:
    operation = app.openapi()["paths"]["/api/v2/workspaces/{workspace_id}/reports/summary"]["get"]
    assert operation["tags"] == ["V2 Reports"]
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "workspace_id", "date_from", "date_until", "category_id", "responsible_user_id",
    }
    assert "requestBody" not in operation


def test_detailed_report_routes_reuse_scope_filters_and_are_read_only() -> None:
    client, _user, workspace, db = _client()
    task_result = {"summary": {"total_count": 3, "pending_count": 1, "completed_count": 1, "not_completed_count": 1, "resolved_count": 2, "completion_rate": "50.00"}, "by_task": [], "by_category": [], "evolution": []}
    progress = {"total_count": 2, "no_iniciado_count": 0, "en_proceso_count": 1, "finalizado_count": 1, "average_progress": "60.00"}
    compliance = {"en_plazo_count": 0, "atrasado_count": 1, "con_adelanto_count": 0, "a_tiempo_count": 1, "con_retraso_count": 0}
    pending_result = {"summary": progress, "compliance": compliance, "by_category": [], "evolution": []}
    project_result = {"summary": progress, "stage_compliance": compliance, "by_category": [], "by_project": [], "evolution": []}
    try:
        with patch("app.api.v2.reports.get_task_report", return_value=task_result) as task_service, patch("app.api.v2.reports.get_pending_item_report", return_value=pending_result), patch("app.api.v2.reports.get_project_report", return_value=project_result):
            assert client.get(f"/api/v2/workspaces/{workspace.id}/reports/tasks", params={"custom_tasks": True}).status_code == 200
            assert client.get(f"/api/v2/workspaces/{workspace.id}/reports/pending-items").status_code == 200
            assert client.get(f"/api/v2/workspaces/{workspace.id}/reports/projects").status_code == 200
        assert task_service.call_args.kwargs["workspace_id"] == workspace.id
        assert task_service.call_args.kwargs["custom_tasks"] is True
        db.add.assert_not_called(); db.flush.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_detailed_reports_reject_reversed_ranges_before_services() -> None:
    client, _user, workspace, _db = _client()
    try:
        with patch("app.api.v2.reports.get_task_report") as service:
            response = client.get(f"/api/v2/workspaces/{workspace.id}/reports/tasks", params={"date_from": "2026-09-02", "date_until": "2026-09-01"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"
        service.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_detailed_report_openapi_contracts_are_get_only() -> None:
    paths = app.openapi()["paths"]
    for suffix in ("tasks", "pending-items", "projects"):
        operations = paths[f"/api/v2/workspaces/{{workspace_id}}/reports/{suffix}"]
        assert set(operations) == {"get"}
        assert "requestBody" not in operations["get"]
