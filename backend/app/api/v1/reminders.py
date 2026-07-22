import uuid

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.reminder import ReminderEvaluationResponse
from app.services import reminder_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/reminders",
    tags=["Reminders"],
)


@router.get("", response_model=ReminderEvaluationResponse)
def evaluate_reminders(
    workspace_id: uuid.UUID,
    evaluated_at: Annotated[AwareDatetime, Query()],
    db: SessionDependency,
    current_user: CurrentUser,
) -> ReminderEvaluationResponse:
    try:
        return reminder_service.evaluate_reminders(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            evaluated_at=evaluated_at,
        )
    except reminder_service.ReminderPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except reminder_service.ReminderTimezoneError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        db.rollback()
        raise
