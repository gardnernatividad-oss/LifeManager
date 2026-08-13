import uuid

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.project import ProjectState
from app.schemas.project_report import ProjectReportResponse
from app.services import project_report_service


router = APIRouter(prefix="/reports/projects", tags=["Project Reports"])


@router.get("", response_model=ProjectReportResponse)
def get_project_report(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
    planned_from: date | None = None,
    planned_to: date | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    state: ProjectState | None = None,
) -> ProjectReportResponse:
    if planned_from is not None and planned_to is not None and planned_from > planned_to:
        raise HTTPException(
            status_code=422,
            detail="planned_from must be on or before planned_to",
        )
    try:
        return project_report_service.get_project_report(
            db,
            workspace_id=workspace.id,
            local_date=local_today(current_user.timezone),
            planned_from=planned_from,
            planned_to=planned_to,
            category_id=category_id,
            is_active=is_active,
            state=state,
        )
    except project_report_service.ProjectReportCategoryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
