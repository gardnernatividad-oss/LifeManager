import uuid

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import User, Workspace, WorkspaceKind
from app.schemas.pending_item import PendingItemCompliance, PendingItemState
from app.schemas.pending_item_report import PendingItemReportResponse
from app.services.pending_item_report_service import PendingItemReportCategoryNotFoundError


def _context(*, timezone: str = "America/Lima"):
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone=timezone, is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    return db, workspace


def _response() -> PendingItemReportResponse:
    return PendingItemReportResponse(
        period={"planned_from": date(2026, 8, 1), "planned_to": date(2026, 8, 31)},
        filters={
            "category_id": None,
            "is_active": True,
            "state": PendingItemState.EN_PROCESO,
            "compliance": PendingItemCompliance.ATRASADO,
        },
        summary={
            "total_count": 2, "active_count": 2, "inactive_count": 0,
            "no_iniciado_count": 0, "en_proceso_count": 2, "finalizado_count": 0,
        },
        compliance={
            "en_plazo_count": 0, "atrasado_count": 2,
            "con_adelanto_count": 0, "a_tiempo_count": 0,
            "con_retraso_count": 0,
        },
        detail={
            "average_atrasado_days": "3.50",
            "average_con_adelanto_days": None,
            "average_con_retraso_days": None,
        },
        by_category=[],
    )


def test_report_passes_filters_local_date_and_serializes_response() -> None:
    db, workspace = _context(timezone="Pacific/Kiritimati")
    category_id = uuid.uuid4()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.pending_item_reports.local_today",
            return_value=date(2026, 8, 13),
        ) as today, patch(
            "app.api.v1.pending_item_reports.pending_item_report_service.get_pending_item_report",
            return_value=_response(),
        ) as service:
            response = client.get(
                "/api/v1/reports/pending-items"
                f"?planned_from=2026-08-01&planned_to=2026-08-31&category_id={category_id}"
                "&is_active=true&state=EN_PROCESO&compliance=ATRASADO"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["summary"]["total_count"] == 2
    assert response.json()["detail"]["average_atrasado_days"] == "3.50"
    today.assert_called_once_with("Pacific/Kiritimati")
    assert service.call_args.args == (db,)
    assert service.call_args.kwargs == {
        "workspace_id": workspace.id,
        "local_date": date(2026, 8, 13),
        "planned_from": date(2026, 8, 1),
        "planned_to": date(2026, 8, 31),
        "category_id": category_id,
        "is_active": True,
        "state": PendingItemState.EN_PROCESO,
        "compliance": PendingItemCompliance.ATRASADO,
    }
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()


def test_reversed_range_is_422_without_service_call() -> None:
    db, _workspace = _context()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.pending_item_reports.pending_item_report_service.get_pending_item_report"
        ) as service:
            response = client.get(
                "/api/v1/reports/pending-items?planned_from=2026-08-31&planned_to=2026-08-01"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    service.assert_not_called()
    db.commit.assert_not_called()


def test_foreign_category_maps_to_safe_404_without_transaction_writes() -> None:
    db, _workspace = _context()
    try:
        with TestClient(app) as client, patch(
            "app.api.v1.pending_item_reports.pending_item_report_service.get_pending_item_report",
            side_effect=PendingItemReportCategoryNotFoundError("Category not found"),
        ):
            response = client.get("/api/v1/reports/pending-items")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_report_requires_authentication_and_valid_enum_filters() -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/reports/pending-items")
    assert unauthenticated.status_code == 401

    _db, _workspace = _context()
    try:
        with TestClient(app) as client:
            invalid_state = client.get(
                "/api/v1/reports/pending-items?state=DESCONOCIDO"
            )
            invalid_compliance = client.get(
                "/api/v1/reports/pending-items?compliance=DESCONOCIDO"
            )
    finally:
        app.dependency_overrides.clear()
    assert invalid_state.status_code == 422
    assert invalid_compliance.status_code == 422
