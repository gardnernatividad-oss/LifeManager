import uuid

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.dependencies import PersonalWorkspace, SessionDependency
from app.schemas.task_report import TaskReportResponse
from app.services import task_report_service


router = APIRouter(prefix="/reports/tasks", tags=["Task Reports"])


@router.get("", response_model=TaskReportResponse)
def get_task_report(
    db: SessionDependency,
    workspace: PersonalWorkspace,
    planned_from: date | None = None,
    planned_to: date | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> TaskReportResponse:
    if planned_from is not None and planned_to is not None and planned_from > planned_to:
        raise HTTPException(
            status_code=422,
            detail="planned_from must be on or before planned_to",
        )
    try:
        return task_report_service.get_task_report(
            db,
            workspace_id=workspace.id,
            planned_from=planned_from,
            planned_to=planned_to,
            master_task_id=master_task_id,
            category_id=category_id,
        )
    except (
        task_report_service.TaskReportMasterTaskNotFoundError,
        task_report_service.TaskReportCategoryNotFoundError,
    ) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
