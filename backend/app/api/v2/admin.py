import uuid

from fastapi import APIRouter, Query, Request

from app.api.v2.dependencies import GlobalAdmin, SessionDependency
from app.api.v2.errors import V2APIError
from app.models.enums import AccountStatus
from app.schemas.v2_identity import (
    AdminAccountStateChange,
    AdminUserList,
    AdminUserSummary,
)
from app.services.rate_limit_service import (
    RateLimitAction,
    RateLimitExceeded,
    RateLimitStorageError,
    enforce_rate_limit,
)
from app.services.v2_admin import (
    change_admin_account_state,
    get_admin_user,
    list_admin_users,
)
from app.services.v2_identity import AccountStateConflictError, AdminAccountNotFoundError


router = APIRouter(prefix="/admin", tags=["V2 Administration"])


def _domain_error(error: Exception) -> V2APIError:
    if isinstance(error, AdminAccountNotFoundError):
        return V2APIError(status_code=404, code="ACCOUNT_NOT_FOUND", message="La cuenta no está disponible.")
    return V2APIError(status_code=409, code="ACCOUNT_STATE_CONFLICT", message="La cuenta cambió o no admite esta acción.")


@router.get("/users", response_model=AdminUserList)
def admin_users(
    db: SessionDependency,
    _admin: GlobalAdmin,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    account_status: AccountStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> AdminUserList:
    result = list_admin_users(
        db,
        page=page,
        page_size=page_size,
        account_status=account_status,
        search=search,
    )
    return AdminUserList(
        items=[AdminUserSummary.model_validate(user) for user in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/users/{user_id}", response_model=AdminUserSummary)
def admin_user(user_id: uuid.UUID, db: SessionDependency, _admin: GlobalAdmin) -> AdminUserSummary:
    try:
        return AdminUserSummary.model_validate(get_admin_user(db, user_id=user_id))
    except AdminAccountNotFoundError as error:
        raise _domain_error(error) from error


def _change_state(
    *,
    user_id: uuid.UUID,
    payload: AdminAccountStateChange,
    new_status: AccountStatus,
    request: Request,
    db: SessionDependency,
    admin: GlobalAdmin,
) -> AdminUserSummary:
    try:
        enforce_rate_limit(action=RateLimitAction.ADMIN_ACCOUNT_STATE, request=request, actor_id=admin.id)
    except RateLimitExceeded as error:
        raise V2APIError(status_code=429, code="RATE_LIMITED", message="Demasiadas operaciones. Inténtalo más tarde.", headers={"Retry-After": str(error.retry_after)}) from error
    except RateLimitStorageError as error:
        raise V2APIError(status_code=503, code="SECURITY_CONTROL_UNAVAILABLE", message="No se pudo validar la operación de forma segura.") from error
    try:
        user = change_admin_account_state(
            db,
            user_id=user_id,
            expected_lock_version=payload.lock_version,
            new_status=new_status,
            actor=admin,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(user)
        return AdminUserSummary.model_validate(user)
    except (AdminAccountNotFoundError, AccountStateConflictError) as error:
        db.rollback()
        raise _domain_error(error) from error
    except Exception:
        db.rollback()
        raise


@router.post("/users/{user_id}/disable", response_model=AdminUserSummary)
def disable_admin_user(user_id: uuid.UUID, payload: AdminAccountStateChange, request: Request, db: SessionDependency, admin: GlobalAdmin) -> AdminUserSummary:
    return _change_state(user_id=user_id, payload=payload, new_status=AccountStatus.DISABLED, request=request, db=db, admin=admin)


@router.post("/users/{user_id}/reactivate", response_model=AdminUserSummary)
def reactivate_admin_user(user_id: uuid.UUID, payload: AdminAccountStateChange, request: Request, db: SessionDependency, admin: GlobalAdmin) -> AdminUserSummary:
    return _change_state(user_id=user_id, payload=payload, new_status=AccountStatus.ACTIVE, request=request, db=db, admin=admin)
