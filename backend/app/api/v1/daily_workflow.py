import uuid

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.daily_workflow import DailyWorkflowResponse
from app.services import daily_workflow_service, task_materialization_service
from app.services.task_series_service import TaskSeriesPermissionError


router = APIRouter(
    prefix="/workspaces/{workspace_id}/daily-workflow",
    tags=["Daily Workflow"],
)


@router.post("/{workflow_date}", response_model=DailyWorkflowResponse)
def initialize_daily_workflow(
    workspace_id: uuid.UUID,
    workflow_date: date,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyWorkflowResponse:
    try:
        result = daily_workflow_service.initialize_daily_workflow(
            db,
            workspace_id=workspace_id,
            workflow_date=workflow_date,
            current_user=current_user,
        )
        db.commit()
    except TaskSeriesPermissionError as error:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (
        task_materialization_service.TaskMaterializationValidationError,
        task_materialization_service.TaskMaterializationConflictError,
    ) as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        db.rollback()
        raise
    return result
