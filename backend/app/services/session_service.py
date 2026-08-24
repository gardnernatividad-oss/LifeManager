from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_and_update_password
from app.models import User
from app.models.enums import AccountStatus


class InvalidCredentialsError(ValueError):
    pass


_DUMMY_PASSWORD_HASH = hash_password("LifeManager timing sentinel password!")


def authenticate_session(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    candidate_hash = user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH
    verified, updated_hash = verify_and_update_password(password, candidate_hash)
    if not verified or user is None or user.account_status != AccountStatus.ACTIVE:
        raise InvalidCredentialsError("Invalid credentials")
    if updated_hash is not None:
        user.hashed_password = updated_hash
        db.flush()
    return user


def invalidate_sessions_after_credential_change(
    _db: Session,
    _user: User,
) -> None:
    """Session credential fingerprints change with the persisted password hash."""
