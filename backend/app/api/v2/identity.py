import uuid

from fastapi import APIRouter, status

from app.api.v2.dependencies import GlobalAdmin, SessionDependency
from app.api.v2.errors import V2APIError
from app.schemas.v2_identity import (
    AdminAccountSummary,
    AdminRegistrationList,
    RegistrationRequestCreate,
    RegistrationRequestAcknowledgement,
    RejectAccountRequest,
)
from app.services.v2_identity import (
    AccountStateConflictError,
    AdminAccountNotFoundError,
    PersonalWorkspaceConflictError,
    RegistrationRequestConflictError,
    approve_registration_request,
    create_registration_request,
    get_admin_account,
    list_pending_registration_requests,
    reject_registration_request,
)


router = APIRouter()


def _service_error(error: Exception) -> V2APIError:
    if isinstance(error, AdminAccountNotFoundError):
        return V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ACCOUNT_NOT_FOUND",
            message="No se encontró la cuenta.",
        )
    if isinstance(error, PersonalWorkspaceConflictError):
        return V2APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="PERSONAL_WORKSPACE_CONFLICT",
            message="La cuenta no puede aprovisionarse en su estado actual.",
        )
    return V2APIError(
        status_code=status.HTTP_409_CONFLICT,
        code="ACCOUNT_STATE_CONFLICT",
        message="La cuenta cambió o no admite esta acción.",
    )


@router.post(
    "/auth/registration-requests",
    response_model=RegistrationRequestAcknowledgement,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["V2 Authentication"],
)
def request_registration(
    registration_in: RegistrationRequestCreate,
    db: SessionDependency,
) -> RegistrationRequestAcknowledgement:
    try:
        create_registration_request(db, registration_in=registration_in)
        db.commit()
    except RegistrationRequestConflictError:
        db.rollback()
        return RegistrationRequestAcknowledgement()
    except Exception:
        db.rollback()
        raise
    return RegistrationRequestAcknowledgement()


@router.get(
    "/admin/account-requests",
    response_model=AdminRegistrationList,
    tags=["V2 Administration"],
)
def pending_registration_requests(
    db: SessionDependency,
    _admin: GlobalAdmin,
) -> AdminRegistrationList:
    users = list_pending_registration_requests(db)
    return AdminRegistrationList(
        items=[AdminAccountSummary.model_validate(user) for user in users],
        total=len(users),
    )


@router.get(
    "/admin/account-requests/{user_id}",
    response_model=AdminAccountSummary,
    tags=["V2 Administration"],
)
def account_request_summary(
    user_id: uuid.UUID,
    db: SessionDependency,
    _admin: GlobalAdmin,
) -> AdminAccountSummary:
    try:
        user = get_admin_account(db, user_id=user_id)
    except AdminAccountNotFoundError as error:
        raise _service_error(error) from error
    return AdminAccountSummary.model_validate(user)


@router.post(
    "/admin/account-requests/{user_id}/approve",
    response_model=AdminAccountSummary,
    tags=["V2 Administration"],
)
def approve_account_request(
    user_id: uuid.UUID,
    db: SessionDependency,
    admin: GlobalAdmin,
) -> AdminAccountSummary:
    try:
        user = approve_registration_request(db, user_id=user_id, actor=admin)
        db.commit()
        db.refresh(user)
    except (
        AccountStateConflictError,
        AdminAccountNotFoundError,
        PersonalWorkspaceConflictError,
    ) as error:
        db.rollback()
        raise _service_error(error) from error
    except Exception:
        db.rollback()
        raise
    return AdminAccountSummary.model_validate(user)


@router.post(
    "/admin/account-requests/{user_id}/reject",
    response_model=AdminAccountSummary,
    tags=["V2 Administration"],
)
def reject_account_request(
    user_id: uuid.UUID,
    rejection_in: RejectAccountRequest,
    db: SessionDependency,
    admin: GlobalAdmin,
) -> AdminAccountSummary:
    try:
        user = reject_registration_request(
            db,
            user_id=user_id,
            actor=admin,
            reason=rejection_in.reason,
        )
        db.commit()
        db.refresh(user)
    except (AccountStateConflictError, AdminAccountNotFoundError) as error:
        db.rollback()
        raise _service_error(error) from error
    except Exception:
        db.rollback()
        raise
    return AdminAccountSummary.model_validate(user)
