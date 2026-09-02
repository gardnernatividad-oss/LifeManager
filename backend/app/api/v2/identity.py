import uuid

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response, status

from app.api.v2.dependencies import GlobalAdmin, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.config import settings
from app.core.client_ip import resolve_client_ip
from app.core.session_security import create_session_token, new_csrf_token
from app.models.user import User
from app.schemas.v2_identity import (
    AuthenticatedAccountRead,
    AdminAccountSummary,
    AdminRegistrationList,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    EmailVerificationResponse,
    LoginRequest,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RegistrationRequestCreate,
    RegistrationRequestAcknowledgement,
    RejectAccountRequest,
)
from app.services.email_delivery import (
    PasswordResetEmail,
    VerificationEmail,
    email_delivery,
)
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
from app.services.password_recovery_service import (
    InvalidPasswordResetTokenError,
    PasswordRecoveryIssuanceConflictError,
    request_password_recovery,
    reset_password,
)
from app.services.session_service import InvalidCredentialsError, authenticate_session
from app.services.rate_limit_service import (
    RateLimitAction,
    RateLimitExceeded,
    RateLimitStorageError,
    enforce_rate_limit,
)
from app.services.anti_bot_service import (
    AntiBotProviderUnavailable,
    AntiBotVerificationFailed,
    verify_anti_bot_token,
)


router = APIRouter()


def _enforce_rate_limit(
    *,
    action: RateLimitAction,
    request: Request,
    email: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    try:
        enforce_rate_limit(
            action=action,
            request=request,
            email=email,
            actor_id=actor_id,
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


def _verify_anti_bot(*, token: str | None, request: Request) -> None:
    try:
        verify_anti_bot_token(
            token=token,
            remote_ip=resolve_client_ip(request),
        )
    except AntiBotVerificationFailed as error:
        raise V2APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="ANTI_BOT_VERIFICATION_FAILED",
            message="No se pudo validar la verificación anti-bot.",
        ) from error
    except AntiBotProviderUnavailable as error:
        raise V2APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SECURITY_CONTROL_UNAVAILABLE",
            message="No se pudo validar la solicitud de forma segura.",
        ) from error


def _set_session_cookies(response: Response, *, user: User) -> None:
    csrf_token = new_csrf_token()
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.SESSION_EXPIRE_MINUTES
    )
    token = create_session_token(
        user_id=user.id,
        hashed_password=user.hashed_password,
        status_changed_at=user.status_changed_at,
        csrf_token=csrf_token,
    )
    common = {
        "max_age": settings.SESSION_EXPIRE_MINUTES * 60,
        "expires": expires,
        "path": "/",
        "secure": settings.session_cookie_secure,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
    }
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        **common,
    )


def _clear_session_cookies(response: Response) -> None:
    for name, httponly in (
        (settings.SESSION_COOKIE_NAME, True),
        (settings.CSRF_COOKIE_NAME, False),
    ):
        response.set_cookie(
            name,
            "",
            max_age=0,
            expires=0,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=httponly,
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )


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
    "/auth/login",
    response_model=AuthenticatedAccountRead,
    tags=["V2 Authentication"],
)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: SessionDependency,
) -> AuthenticatedAccountRead:
    _enforce_rate_limit(
        action=RateLimitAction.LOGIN,
        request=request,
        email=str(credentials.email),
    )
    try:
        user = authenticate_session(
            db,
            email=str(credentials.email),
            password=credentials.password,
        )
        db.commit()
        db.refresh(user)
    except InvalidCredentialsError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Correo o contraseña incorrectos.",
        ) from error
    except Exception:
        db.rollback()
        raise
    _set_session_cookies(response, user=user)
    return AuthenticatedAccountRead.model_validate(user)


@router.get(
    "/me",
    response_model=AuthenticatedAccountRead,
    tags=["V2 Authentication"],
)
def current_account(account: UsableAccount) -> AuthenticatedAccountRead:
    return AuthenticatedAccountRead.model_validate(account)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["V2 Authentication"],
)
def logout(response: Response) -> None:
    _clear_session_cookies(response)


@router.post(
    "/auth/registration-requests",
    response_model=RegistrationRequestAcknowledgement,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["V2 Authentication"],
)
def request_registration(
    registration_in: RegistrationRequestCreate,
    request: Request,
    db: SessionDependency,
) -> RegistrationRequestAcknowledgement:
    _enforce_rate_limit(
        action=RateLimitAction.REGISTRATION,
        request=request,
        email=str(registration_in.email),
    )
    _verify_anti_bot(token=registration_in.turnstile_token, request=request)
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
    request: Request,
    db: SessionDependency,
) -> EmailVerificationResponse:
    _enforce_rate_limit(
        action=RateLimitAction.VERIFICATION_SUBMIT,
        request=request,
    )
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
    request: Request,
    db: SessionDependency,
) -> RegistrationRequestAcknowledgement:
    _enforce_rate_limit(
        action=RateLimitAction.VERIFICATION_RESEND,
        request=request,
        email=str(resend_in.email),
    )
    _verify_anti_bot(token=resend_in.turnstile_token, request=request)
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


@router.post(
    "/auth/password-recovery-requests",
    response_model=RegistrationRequestAcknowledgement,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["V2 Authentication"],
)
def request_password_reset(
    recovery_in: PasswordRecoveryRequest,
    request: Request,
    db: SessionDependency,
) -> RegistrationRequestAcknowledgement:
    _enforce_rate_limit(
        action=RateLimitAction.PASSWORD_RECOVERY,
        request=request,
        email=str(recovery_in.email),
    )
    _verify_anti_bot(token=recovery_in.turnstile_token, request=request)
    try:
        issued = request_password_recovery(db, email=str(recovery_in.email))
        db.commit()
    except PasswordRecoveryIssuanceConflictError:
        db.rollback()
        return RegistrationRequestAcknowledgement()
    except Exception:
        db.rollback()
        raise
    if issued is not None:
        email_delivery.send_password_reset_email(
            PasswordResetEmail(
                recipient=issued.recipient,
                raw_token=issued.raw_token,
            )
        )
    return RegistrationRequestAcknowledgement()


@router.post(
    "/auth/password-resets",
    response_model=PasswordResetResponse,
    tags=["V2 Authentication"],
)
def perform_password_reset(
    reset_in: PasswordResetRequest,
    request: Request,
    db: SessionDependency,
) -> PasswordResetResponse:
    _enforce_rate_limit(
        action=RateLimitAction.PASSWORD_RESET,
        request=request,
    )
    try:
        reset_password(
            db,
            raw_token=reset_in.token,
            new_password=reset_in.new_password,
        )
        db.commit()
    except InvalidPasswordResetTokenError as error:
        db.rollback()
        raise V2APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PASSWORD_RESET_TOKEN",
            message="El enlace para restablecer la contraseña no es válido.",
        ) from error
    except Exception:
        db.rollback()
        raise
    return PasswordResetResponse()


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
    request: Request,
    db: SessionDependency,
    admin: GlobalAdmin,
) -> AdminAccountSummary:
    _enforce_rate_limit(
        action=RateLimitAction.ADMIN_APPROVE,
        request=request,
        actor_id=admin.id,
    )
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
    request: Request,
    db: SessionDependency,
    admin: GlobalAdmin,
) -> AdminAccountSummary:
    _enforce_rate_limit(
        action=RateLimitAction.ADMIN_REJECT,
        request=request,
        actor_id=admin.id,
    )
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
