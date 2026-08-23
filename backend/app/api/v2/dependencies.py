import uuid

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v2.errors import V2APIError
from app.core.tokens import decode_access_token
from app.db.session import SessionLocal
from app.models import User, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, MembershipStatus


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v2/auth/login",
    auto_error=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDependency = Annotated[Session, Depends(get_db)]


def _authentication_error() -> V2APIError:
    return V2APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="INVALID_SESSION",
        message="No se pudo validar la sesión.",
    )


def get_current_account(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: SessionDependency,
) -> User:
    subject = decode_access_token(token)
    try:
        user_id = uuid.UUID(subject) if subject is not None else None
    except (TypeError, ValueError):
        user_id = None
    if user_id is None:
        raise _authentication_error()

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _authentication_error()
    return user


CurrentAccount = Annotated[User, Depends(get_current_account)]


def require_usable_account(current_account: CurrentAccount) -> User:
    if current_account.account_status != AccountStatus.ACTIVE:
        raise _authentication_error()
    return current_account


UsableAccount = Annotated[User, Depends(require_usable_account)]


def require_global_admin(current_account: UsableAccount) -> User:
    if current_account.global_role != GlobalRole.GLOBAL_ADMIN:
        raise V2APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="GLOBAL_ADMIN_REQUIRED",
            message="No tienes permiso para realizar esta acción.",
        )
    return current_account


GlobalAdmin = Annotated[User, Depends(require_global_admin)]


def find_active_membership(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> WorkspaceMember | None:
    """Resolve private Workspace access without any global-role bypass."""
    return db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
    )
