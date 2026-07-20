import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User | None:
    normalized_email = str(email).strip().lower()
    statement = select(User).where(User.email == normalized_email)
    user = db.scalar(statement)

    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user


def register_user(
    db: Session,
    *,
    user_in: UserCreate,
) -> User:
    normalized_email = str(user_in.email).lower()
    statement = select(User).where(User.email == normalized_email)
    if db.scalar(statement) is not None:
        raise ValueError("Email already registered")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        is_active=True,
        is_verified=False,
        username=uuid.uuid4().hex,
        full_name=(
            f"{user_in.first_name.strip()} {user_in.last_name.strip()}".strip()
        ),
    )
    db.add(user)
    db.flush()

    return user
