import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.dashboard import DashboardStatistics, DashboardSummary
from app.services import dashboard_service, dashboard_statistics_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/dashboard",
    tags=["Dashboard"],
)


@router.get("", response_model=DashboardSummary)
def get_dashboard_summary(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DashboardSummary:
    try:
        return dashboard_service.get_dashboard_summary(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except dashboard_service.DashboardPermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error


@router.get("/statistics", response_model=DashboardStatistics)
def get_dashboard_statistics(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DashboardStatistics:
    try:
        return dashboard_statistics_service.get_dashboard_statistics(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except dashboard_statistics_service.DashboardStatisticsPermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
