from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.user_settings import UserSettingsRead, UserSettingsReplace
from app.services import user_settings_service


router = APIRouter(prefix="/users/me/settings", tags=["User Settings"])


def _commit_settings(db, operation, **kwargs) -> UserSettingsRead:
    try:
        settings = operation(db, **kwargs); db.commit(); db.refresh(settings)
    except user_settings_service.UserSettingsValidationError as error:
        db.rollback(); raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception:
        db.rollback(); raise
    return UserSettingsRead.model_validate(settings)


@router.get("", response_model=UserSettingsRead)
def get_user_settings(db: SessionDependency, current_user: CurrentUser) -> UserSettingsRead:
    return _commit_settings(db, user_settings_service.get_or_create_user_settings, current_user=current_user)


@router.put("", response_model=UserSettingsRead)
def replace_user_settings(settings_in: UserSettingsReplace, db: SessionDependency, current_user: CurrentUser) -> UserSettingsRead:
    return _commit_settings(db, user_settings_service.replace_user_settings, current_user=current_user, settings_in=settings_in)
