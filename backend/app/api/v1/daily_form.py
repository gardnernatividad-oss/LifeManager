import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.daily_form import DailyFormDefinition
from app.schemas.daily_form import DailyFormDefinitionRead, DailyFormDefinitionReplace
from app.services import daily_form_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/daily-form",
    tags=["Daily Form"],
)


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, daily_form_service.DailyFormNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise HTTPException(status_code=403, detail=str(error)) from error


@router.get("", response_model=DailyFormDefinitionRead)
def get_daily_form_definition(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyFormDefinitionRead:
    try:
        definition = daily_form_service.get_daily_form_definition(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except (
        daily_form_service.DailyFormNotFoundError,
        daily_form_service.DailyFormPermissionError,
    ) as error:
        _raise_http_error(error)
    return DailyFormDefinitionRead.model_validate(definition)


@router.put("", response_model=DailyFormDefinitionRead)
def replace_daily_form_definition(
    workspace_id: uuid.UUID,
    definition_in: DailyFormDefinitionReplace,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyFormDefinitionRead:
    try:
        definition = daily_form_service.replace_daily_form_definition(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            definition_in=definition_in,
        )
        db.commit()
        db.refresh(definition)
    except (
        daily_form_service.DailyFormNotFoundError,
        daily_form_service.DailyFormPermissionError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return DailyFormDefinitionRead.model_validate(definition)
