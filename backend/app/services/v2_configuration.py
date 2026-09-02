import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import AccountStatus
from app.core.security import hash_password, verify_password
from app.schemas.v2_configuration import PasswordChange, ProfileUpdate


class ProfileConflictError(ValueError):
    pass


class CurrentPasswordIncorrectError(ValueError):
    pass


def update_profile(
    db: Session,
    *,
    account_id: uuid.UUID,
    profile_in: ProfileUpdate,
) -> User:
    account = db.scalar(select(User).where(User.id == account_id).with_for_update())
    if account is None or account.account_status != AccountStatus.ACTIVE:
        raise ProfileConflictError("Account cannot be updated")
    if account.lock_version != profile_in.lock_version:
        raise ProfileConflictError("Profile changed concurrently")

    account.first_name = profile_in.first_name
    account.last_name = profile_in.last_name
    account.timezone = profile_in.timezone
    account.lock_version += 1
    db.flush()
    return account


def change_password(
    db: Session,
    *,
    account_id: uuid.UUID,
    password_in: PasswordChange,
) -> User:
    account = db.scalar(select(User).where(User.id == account_id).with_for_update())
    if account is None or account.account_status != AccountStatus.ACTIVE:
        raise ProfileConflictError("Account cannot be updated")
    if not verify_password(password_in.current_password, account.hashed_password):
        raise CurrentPasswordIncorrectError("Current password is incorrect")

    account.hashed_password = hash_password(password_in.new_password)
    db.flush()
    return account
