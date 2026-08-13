import uuid

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import User, Workspace, WorkspaceKind
from app.schemas.project import ProjectState
from app.schemas.project_report import ProjectReportResponse
from app.services.project_report_service import ProjectReportCategoryNotFoundError


def _context(*, timezone: str = "America/Lima"):
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone=timezone, is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    return db, workspace


def _response() -> ProjectReportResponse:
    return ProjectReportResponse(
        period={"planned_from": date(2026, 8, 4), "planned_to": date(2026, 8, 15)},
        filters={"category_id": None, "is_active": True, "state": ProjectState.EN_PROCESO},
        summary={
            "total_count": 1, "active_count": 1, "inactive_count": 0,
            "no_iniciado_count": 0, "en_proceso_count": 1, "finalizado_count": 0,
        },
        step_compliance={
            "en_plazo_count": 1, "atrasado_count": 1,
            "con_adelanto_count": 0, "a_tiempo_count": 0,
            "con_retraso_count": 0,
        },
        detail={
            "average_atrasado_days": "2.00",
            "average_con_adelanto_days": None,
            "average_con_retraso_days": None,
        },
        by_project=[],
    )


def test_project_report_passes_filters_timezone_and_serializes() -> None:
    db, workspace = _context(timezone="Pacific/Kiritimati")
    category_id = uuid.uuid4()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.project_reports.local_today", return_value=date(2026, 8, 13)
        ) as today, patch(
            "app.api.v1.project_reports.project_report_service.get_project_report",
            return_value=_response(),
        ) as service:
            response = client.get(
                "/api/v1/reports/projects"
                f"?planned_from=2026-08-04&planned_to=2026-08-15&category_id={category_id}"
                "&is_active=true&state=EN_PROCESO"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["summary"]["en_proceso_count"] == 1
    assert response.json()["detail"]["average_atrasado_days"] == "2.00"
    today.assert_called_once_with("Pacific/Kiritimati")
    assert service.call_args.args == (db,)
    assert service.call_args.kwargs == {
        "workspace_id": workspace.id,
        "local_date": date(2026, 8, 13),
        "planned_from": date(2026, 8, 4),
        "planned_to": date(2026, 8, 15),
        "category_id": category_id,
        "is_active": True,
        "state": ProjectState.EN_PROCESO,
    }
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()


def test_reversed_period_returns_422_without_service_call() -> None:
    db, _workspace = _context()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.project_reports.project_report_service.get_project_report"
        ) as service:
            response = client.get(
                "/api/v1/reports/projects?planned_from=2026-08-15&planned_to=2026-08-04"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    service.assert_not_called()
    db.commit.assert_not_called()


def test_foreign_category_maps_to_safe_404_read_only() -> None:
    db, _workspace = _context()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.project_reports.project_report_service.get_project_report",
            side_effect=ProjectReportCategoryNotFoundError("Category not found"),
        ):
            response = client.get("/api/v1/reports/projects")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_project_report_requires_authentication_and_valid_state() -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/reports/projects")
    assert unauthenticated.status_code == 401

    _db, _workspace = _context()
    try:
        with TestClient(app) as client:
            invalid = client.get("/api/v1/reports/projects?state=DESCONOCIDO")
    finally:
        app.dependency_overrides.clear()
    assert invalid.status_code == 422
