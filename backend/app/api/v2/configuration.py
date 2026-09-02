from zoneinfo import available_timezones

from fastapi import APIRouter, Request, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.schemas.v2_configuration import PasswordChange, ProfileRead, ProfileUpdate, TimezoneList
from app.services.rate_limit_service import (
    RateLimitAction,
    RateLimitExceeded,
    RateLimitStorageError,
    enforce_rate_limit,
)
from app.services.v2_configuration import (
    CurrentPasswordIncorrectError,
    ProfileConflictError,
    change_password,
    update_profile,
)


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


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def patch_password(
    password_in: PasswordChange,
    request: Request,
    db: SessionDependency,
    account: UsableAccount,
) -> None:
    try:
        enforce_rate_limit(
            action=RateLimitAction.PASSWORD_CHANGE,
            request=request,
            actor_id=account.id,
        )
    except RateLimitExceeded as error:
        raise V2APIError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="Demasiados intentos. Inténtalo nuevamente más tarde.",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    except RateLimitStorageError as error:
        raise V2APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SECURITY_CONTROL_UNAVAILABLE",
            message="No se pudo validar la solicitud de forma segura.",
        ) from error

    try:
        change_password(db, account_id=account.id, password_in=password_in)
        db.commit()
    except CurrentPasswordIncorrectError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CURRENT_PASSWORD_INCORRECT",
            message="La contraseña actual no es correcta.",
        ) from error
    except ProfileConflictError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="ACCOUNT_STATE_CONFLICT",
            message="La cuenta cambió o no admite esta acción.",
        ) from error
    except Exception:
        db.rollback()
        raise
