import hmac
import uuid

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import AccountActionToken, User
from app.models.enums import AccountActionTokenType, AccountStatus
from app.services.account_action_token_service import (
    ACTION_TOKEN_LENGTH,
    digest_action_token,
    generate_action_token,
    is_well_formed_action_token,
)


PASSWORD_RESET_TOKEN_LENGTH = ACTION_TOKEN_LENGTH
PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)


class InvalidPasswordResetTokenError(ValueError):
    pass


class PasswordRecoveryIssuanceConflictError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedPasswordReset:
    recipient: str
    raw_token: str
    expires_at: datetime


SessionInvalidationHook = Callable[[Session, User], None]


def _no_session_invalidation(_db: Session, _user: User) -> None:
    """Stage 2.8 will replace this boundary with session invalidation."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_active_token_unique_violation(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    return (
        getattr(diagnostic, "constraint_name", None)
        == "uq_account_tokens_active_user_type"
    )


def _revoke_active_password_reset_tokens(
    db: Session,
    *,
    user_id: uuid.UUID,
    revoked_at: datetime,
) -> None:
    db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user_id,
            AccountActionToken.token_type == AccountActionTokenType.PASSWORD_RESET,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )


def issue_password_reset_token(
    db: Session,
    *,
    user: User,
    now: datetime | None = None,
) -> IssuedPasswordReset:
    issued_at = now or _now()
    if user.account_status != AccountStatus.ACTIVE:
        raise InvalidPasswordResetTokenError("Account is not eligible")
    raw_token = generate_action_token()
    expires_at = issued_at + PASSWORD_RESET_TOKEN_TTL
    db.add(
        AccountActionToken(
            user_id=user.id,
            token_type=AccountActionTokenType.PASSWORD_RESET,
            token_digest=digest_action_token(raw_token),
            expires_at=expires_at,
            created_at=issued_at,
        )
    )
    try:
        db.flush()
    except IntegrityError as error:
        if _is_active_token_unique_violation(error):
            raise PasswordRecoveryIssuanceConflictError(
                "A concurrent reset token was issued"
            ) from error
        raise
    return IssuedPasswordReset(
        recipient=user.email,
        raw_token=raw_token,
        expires_at=expires_at,
    )


def request_password_recovery(
    db: Session,
    *,
    email: str,
) -> IssuedPasswordReset | None:
    normalized_email = email.strip().lower()
    user_id = db.scalar(select(User.id).where(User.email == normalized_email))
    if user_id is None:
        return None
    active_tokens = list(
        db.scalars(
            select(AccountActionToken)
            .where(
                AccountActionToken.user_id == user_id,
                AccountActionToken.token_type
                == AccountActionTokenType.PASSWORD_RESET,
                AccountActionToken.consumed_at.is_(None),
                AccountActionToken.revoked_at.is_(None),
            )
            .order_by(AccountActionToken.id)
            .with_for_update()
        ).all()
    )
    user = db.scalar(
        select(User)
        .where(User.id == user_id, User.email == normalized_email)
        .with_for_update()
    )
    if user is None or user.account_status != AccountStatus.ACTIVE:
        return None
    revoked_at = _now()
    for token in active_tokens:
        token.revoked_at = revoked_at
    db.flush()
    return issue_password_reset_token(db, user=user)


def reset_password(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
    now: datetime | None = None,
    session_invalidation_hook: SessionInvalidationHook = _no_session_invalidation,
) -> User:
    reset_at = now or _now()
    if not is_well_formed_action_token(raw_token):
        raise InvalidPasswordResetTokenError("Invalid password reset token")
    supplied_digest = digest_action_token(raw_token)
    identified = db.execute(
        select(AccountActionToken.id, AccountActionToken.user_id).where(
            AccountActionToken.token_type == AccountActionTokenType.PASSWORD_RESET,
            AccountActionToken.token_digest == supplied_digest,
        )
    ).one_or_none()
    if identified is None:
        raise InvalidPasswordResetTokenError("Invalid password reset token")

    token = db.scalar(
        select(AccountActionToken)
        .where(AccountActionToken.id == identified.id)
        .with_for_update()
    )
    if (
        token is None
        or token.token_type != AccountActionTokenType.PASSWORD_RESET
        or token.consumed_at is not None
        or token.revoked_at is not None
        or token.expires_at <= reset_at
        or not hmac.compare_digest(token.token_digest, supplied_digest)
    ):
        raise InvalidPasswordResetTokenError("Invalid password reset token")

    user = db.scalar(
        select(User).where(User.id == identified.user_id).with_for_update()
    )
    if user is None or user.account_status != AccountStatus.ACTIVE:
        raise InvalidPasswordResetTokenError("Invalid password reset token")

    user.hashed_password = hash_password(new_password)
    token.consumed_at = reset_at
    _revoke_active_password_reset_tokens(
        db,
        user_id=user.id,
        revoked_at=reset_at,
    )
    token.revoked_at = None
    session_invalidation_hook(db, user)
    db.flush()
    return user

