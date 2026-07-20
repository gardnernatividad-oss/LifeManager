import uuid

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDependency = Annotated[Session, Depends(get_db)]


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: SessionDependency,
) -> User:
    subject = decode_access_token(token)
    if subject is None:
        raise _credentials_exception()

    try:
        user_id = uuid.UUID(subject)
    except (AttributeError, TypeError, ValueError) as error:
        raise _credentials_exception() from error

    statement = select(User).where(User.id == user_id)
    user = db.scalar(statement)
    if user is None or not user.is_active:
        raise _credentials_exception()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
