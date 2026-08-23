import uuid

from fastapi import APIRouter, status

from app.api.v2.dependencies import GlobalAdmin, SessionDependency
from app.api.v2.errors import V2APIError
from app.schemas.v2_identity import (
    AdminAccountSummary,
    AdminRegistrationList,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    EmailVerificationResponse,
    RegistrationRequestCreate,
    RegistrationRequestAcknowledgement,
    RejectAccountRequest,
)
from app.services.email_delivery import VerificationEmail, email_delivery
from app.services.email_verification_service import (
    InvalidEmailVerificationTokenError,
    create_registration_with_verification,
    resend_email_verification,
    verify_email_token,
)
from app.services.v2_identity import (
    AccountStateConflictError,
    AdminAccountNotFoundError,
    PersonalWorkspaceConflictError,
    RegistrationRequestConflictError,
    approve_registration_request,
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
    issued = None
    try:
        issued = create_registration_with_verification(
            db,
            registration_in=registration_in,
        )
        db.commit()
    except RegistrationRequestConflictError:
        db.rollback()
        return RegistrationRequestAcknowledgement()
    except Exception:
        db.rollback()
        raise
    if issued is not None:
        email_delivery.send_verification_email(
            VerificationEmail(
                recipient=issued.recipient,
                raw_token=issued.raw_token,
            )
        )
    return RegistrationRequestAcknowledgement()


@router.post(
    "/auth/email-verifications",
    response_model=EmailVerificationResponse,
    tags=["V2 Authentication"],
)
def verify_email(
    verification_in: EmailVerificationRequest,
    db: SessionDependency,
) -> EmailVerificationResponse:
    try:
        verify_email_token(db, raw_token=verification_in.token)
        db.commit()
    except InvalidEmailVerificationTokenError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_EMAIL_VERIFICATION_TOKEN",
            message="El enlace de verificación no es válido.",
        ) from error
    except Exception:
        db.rollback()
        raise
    return EmailVerificationResponse()


@router.post(
    "/auth/email-verifications/resend",
    response_model=RegistrationRequestAcknowledgement,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["V2 Authentication"],
)
def resend_verification(
    resend_in: EmailVerificationResendRequest,
    db: SessionDependency,
) -> RegistrationRequestAcknowledgement:
    try:
        issued = resend_email_verification(db, email=str(resend_in.email))
        db.commit()
    except Exception:
        db.rollback()
        raise
    if issued is not None:
        email_delivery.send_verification_email(
            VerificationEmail(
                recipient=issued.recipient,
                raw_token=issued.raw_token,
            )
        )
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
