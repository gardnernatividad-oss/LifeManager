import hashlib
import hmac
import re
import secrets
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AccountActionToken, User
from app.models.enums import AccountActionTokenType, AccountStatus
from app.schemas.v2_identity import RegistrationRequestCreate
from app.services.v2_identity import (
    create_registration_request,
    transition_account_state,
)


EMAIL_VERIFICATION_TOKEN_BYTES = 32
EMAIL_VERIFICATION_TOKEN_LENGTH = 43
EMAIL_VERIFICATION_TOKEN_TTL = timedelta(hours=24)
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class InvalidEmailVerificationTokenError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedEmailVerification:
    recipient: str
    raw_token: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def digest_action_token(raw_token: str) -> bytes:
    return hashlib.sha256(raw_token.encode("ascii")).digest()


def _new_raw_token() -> str:
    raw_token = secrets.token_urlsafe(EMAIL_VERIFICATION_TOKEN_BYTES)
    if len(raw_token) != EMAIL_VERIFICATION_TOKEN_LENGTH:
        raise RuntimeError("Unexpected action-token length")
    return raw_token


def _revoke_active_verification_tokens(
    db: Session,
    *,
    user_id: uuid.UUID,
    revoked_at: datetime,
) -> None:
    db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user_id,
            AccountActionToken.token_type
            == AccountActionTokenType.EMAIL_VERIFICATION,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )


def issue_email_verification_token(
    db: Session,
    *,
    user: User,
    now: datetime | None = None,
    revoke_existing: bool = False,
) -> IssuedEmailVerification:
    issued_at = now or _now()
    if user.account_status != AccountStatus.PENDING_EMAIL_VERIFICATION:
        raise InvalidEmailVerificationTokenError("Account is not eligible")
    if revoke_existing:
        _revoke_active_verification_tokens(
            db,
            user_id=user.id,
            revoked_at=issued_at,
        )

    raw_token = _new_raw_token()
    expires_at = issued_at + EMAIL_VERIFICATION_TOKEN_TTL
    db.add(
        AccountActionToken(
            user_id=user.id,
            token_type=AccountActionTokenType.EMAIL_VERIFICATION,
            token_digest=digest_action_token(raw_token),
            expires_at=expires_at,
            created_at=issued_at,
        )
    )
    db.flush()
    return IssuedEmailVerification(
        recipient=user.email,
        raw_token=raw_token,
        expires_at=expires_at,
    )


def create_registration_with_verification(
    db: Session,
    *,
    registration_in: RegistrationRequestCreate,
) -> IssuedEmailVerification:
    user = create_registration_request(db, registration_in=registration_in)
    return issue_email_verification_token(db, user=user)


def resend_email_verification(
    db: Session,
    *,
    email: str,
) -> IssuedEmailVerification | None:
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
                == AccountActionTokenType.EMAIL_VERIFICATION,
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
    if (
        user is None
        or user.account_status != AccountStatus.PENDING_EMAIL_VERIFICATION
    ):
        return None
    revoked_at = _now()
    for token in active_tokens:
        token.revoked_at = revoked_at
    db.flush()
    return issue_email_verification_token(
        db,
        user=user,
    )


def verify_email_token(
    db: Session,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> User:
    verified_at = now or _now()
    if not _TOKEN_PATTERN.fullmatch(raw_token):
        raise InvalidEmailVerificationTokenError("Invalid verification token")

    supplied_digest = digest_action_token(raw_token)
    identified = db.execute(
        select(AccountActionToken.id, AccountActionToken.user_id).where(
            AccountActionToken.token_type
            == AccountActionTokenType.EMAIL_VERIFICATION,
            AccountActionToken.token_digest == supplied_digest,
        )
    ).one_or_none()
    if identified is None:
        raise InvalidEmailVerificationTokenError("Invalid verification token")

    token = db.scalar(
        select(AccountActionToken)
        .where(AccountActionToken.id == identified.id)
        .with_for_update()
    )
    if (
        token is None
        or token.token_type != AccountActionTokenType.EMAIL_VERIFICATION
        or token.consumed_at is not None
        or token.revoked_at is not None
        or token.expires_at <= verified_at
        or not hmac.compare_digest(token.token_digest, supplied_digest)
    ):
        raise InvalidEmailVerificationTokenError("Invalid verification token")

    user = db.scalar(
        select(User).where(User.id == identified.user_id).with_for_update()
    )
    if (
        user is None
        or user.account_status != AccountStatus.PENDING_EMAIL_VERIFICATION
        or user.email_verified_at is not None
    ):
        raise InvalidEmailVerificationTokenError("Invalid verification token")

    user.email_verified_at = verified_at
    transition_account_state(
        db,
        user=user,
        new_status=AccountStatus.PENDING_APPROVAL,
        actor_user_id=None,
        reason="EMAIL_VERIFIED",
    )
    token.consumed_at = verified_at
    _revoke_active_verification_tokens(
        db,
        user_id=user.id,
        revoked_at=verified_at,
    )
    token.revoked_at = None
    db.flush()
    return user
