import uuid

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import User, Workspace, WorkspaceKind
from app.schemas.task_report import TaskReportResponse
from app.services.task_report_service import (
    TaskReportCategoryNotFoundError,
    TaskReportMasterTaskNotFoundError,
)


def _context():
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    return db, workspace


def test_task_report_passes_custom_filters_and_serializes_decimal_metrics() -> None:
    db, workspace = _context(); master_id = uuid.uuid4(); category_id = uuid.uuid4()
    response_model = TaskReportResponse(
        period={"planned_from": date(2026, 8, 4), "planned_to": date(2026, 8, 15)},
        summary={"completed_count": 3, "not_completed_count": 1,
                 "terminal_count": 4, "completion_rate": Decimal("75.00")},
        by_master_task=[],
    )
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.task_reports.task_report_service.get_task_report",
            return_value=response_model,
        ) as service:
            response = client.get(
                f"/api/v1/reports/tasks?planned_from=2026-08-04&planned_to=2026-08-15"
                f"&master_task_id={master_id}&category_id={category_id}"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["summary"] == {
        "completed_count": 3, "not_completed_count": 1,
        "terminal_count": 4, "completion_rate": "75.00",
    }
    assert service.call_args.kwargs == {
        "workspace_id": workspace.id,
        "planned_from": date(2026, 8, 4), "planned_to": date(2026, 8, 15),
        "master_task_id": master_id, "category_id": category_id,
    }
    assert service.call_args.args == (db,)
    db.flush.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_invalid_range_is_422_without_service_call() -> None:
    db, _workspace = _context()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.task_reports.task_report_service.get_task_report"
        ) as service:
            response = client.get(
                "/api/v1/reports/tasks?planned_from=2026-08-15&planned_to=2026-08-04"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    service.assert_not_called(); db.commit.assert_not_called()


def test_foreign_master_or_category_maps_to_safe_404() -> None:
    for error in (
        TaskReportMasterTaskNotFoundError("Master task not found"),
        TaskReportCategoryNotFoundError("Category not found"),
    ):
        db, _workspace = _context()
        try:
            with TestClient(app) as client, patch(
                "app.api.v1.task_reports.task_report_service.get_task_report",
                side_effect=error,
            ):
                response = client.get("/api/v1/reports/tasks")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 404
        db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_task_report_requires_authentication_and_has_no_category_breakdown() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/tasks")
    assert response.status_code == 401
    assert "by_category" not in TaskReportResponse.model_json_schema()["properties"]
