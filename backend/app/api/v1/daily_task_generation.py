import uuid

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.services import daily_task_generation_service, task_materialization_service
from app.services.task_series_service import TaskSeriesPermissionError


router = APIRouter(
    prefix="/workspaces/{workspace_id}/daily-task-generation",
    tags=["Daily Task Generation"],
)


@router.post("/{generation_date}", response_model=DailyTaskGenerationResponse)
def generate_daily_tasks(
    workspace_id: uuid.UUID,
    generation_date: date,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyTaskGenerationResponse:
    try:
        result = daily_task_generation_service.generate_daily_tasks(
            db,
            workspace_id=workspace_id,
            generation_date=generation_date,
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
