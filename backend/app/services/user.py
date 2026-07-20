import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


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
