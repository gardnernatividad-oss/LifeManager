import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.daily_form import DailyFormDefinition
from app.schemas.daily_form import DailyFormDefinitionRead, DailyFormDefinitionReplace
from app.schemas.daily_form_submission import DailyFormSubmissionRead, DailyFormSubmissionReplace
from app.services import daily_form_service, daily_form_submission_service


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


def _raise_submission_error(error: Exception) -> None:
    if isinstance(error, daily_form_submission_service.DailyFormSubmissionNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, daily_form_submission_service.DailyFormSubmissionPermissionError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, daily_form_submission_service.DailyFormDefinitionRequiredError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/submissions/{submission_date}", response_model=DailyFormSubmissionRead)
def get_daily_form_submission(
    workspace_id: uuid.UUID,
    submission_date: date,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyFormSubmissionRead:
    try:
        submission = daily_form_submission_service.get_daily_form_submission(
            db, workspace_id=workspace_id, submission_date=submission_date, current_user=current_user,
        )
    except (
        daily_form_submission_service.DailyFormSubmissionNotFoundError,
        daily_form_submission_service.DailyFormSubmissionPermissionError,
    ) as error:
        _raise_submission_error(error)
    return DailyFormSubmissionRead.from_submission(submission)


@router.put("/submissions/{submission_date}", response_model=DailyFormSubmissionRead)
def replace_daily_form_submission(
    workspace_id: uuid.UUID,
    submission_date: date,
    submission_in: DailyFormSubmissionReplace,
    db: SessionDependency,
    current_user: CurrentUser,
) -> DailyFormSubmissionRead:
    try:
        submission = daily_form_submission_service.replace_daily_form_submission(
            db, workspace_id=workspace_id, submission_date=submission_date,
            current_user=current_user, submission_in=submission_in,
        )
        db.commit()
        db.refresh(submission)
    except (
        daily_form_submission_service.DailyFormSubmissionPermissionError,
        daily_form_submission_service.DailyFormDefinitionRequiredError,
        daily_form_submission_service.DailyFormSubmissionValidationError,
    ) as error:
        db.rollback()
        _raise_submission_error(error)
    except Exception:
        db.rollback()
        raise
    return DailyFormSubmissionRead.from_submission(submission)
