from zoneinfo import available_timezones

from fastapi import APIRouter, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.schemas.v2_configuration import ProfileRead, ProfileUpdate, TimezoneList
from app.services.v2_configuration import ProfileConflictError, update_profile


router = APIRouter(prefix="/configuration", tags=["V2 Configuration"])


@router.get("/profile", response_model=ProfileRead)
def get_profile(account: UsableAccount) -> ProfileRead:
    return ProfileRead.model_validate(account)


@router.patch("/profile", response_model=ProfileRead)
def patch_profile(
    profile_in: ProfileUpdate,
    db: SessionDependency,
    account: UsableAccount,
) -> ProfileRead:
    try:
        updated = update_profile(db, account_id=account.id, profile_in=profile_in)
        db.commit()
        db.refresh(updated)
    except ProfileConflictError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="PROFILE_CONFLICT",
            message="El perfil cambió. Actualiza e intenta nuevamente.",
        ) from error
    except Exception:
        db.rollback()
        raise
    return ProfileRead.model_validate(updated)


@router.get("/timezones", response_model=TimezoneList)
def get_timezones(_account: UsableAccount) -> TimezoneList:
    return TimezoneList(items=sorted(available_timezones()))
