import uuid

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v2.errors import V2APIError
from app.core.config import settings
from app.core.session_security import (
    decode_session_token,
    session_matches_password,
)
from app.db.session import SessionLocal
from app.models import User, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, MembershipStatus
from app.services.v2_workspace import (
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
    WorkspaceOwnerRequiredError,
    require_workspace_owner as require_owner_access,
    resolve_active_workspace_access,
)


session_cookie = APIKeyCookie(
    name=settings.SESSION_COOKIE_NAME,
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
    request: Request,
    token: Annotated[str | None, Depends(session_cookie)],
    db: SessionDependency,
) -> User:
    claims = decode_session_token(token)
    if claims is None:
        raise _authentication_error()

    user = db.scalar(select(User).where(User.id == claims.user_id))
    if (
        user is None
        or user.account_status != AccountStatus.ACTIVE
        or not session_matches_password(claims, user.hashed_password, user.status_changed_at)
    ):
        raise _authentication_error()
    request.state.session_claims = claims
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


def require_active_workspace_membership(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceAccess:
    try:
        return resolve_active_workspace_access(
            db,
            account=current_account,
            workspace_id=workspace_id,
        )
    except WorkspaceAccessNotFoundError as error:
        raise V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="WORKSPACE_NOT_FOUND",
            message="No se encontró el espacio de trabajo.",
        ) from error


ActiveWorkspaceMembership = Annotated[
    WorkspaceAccess,
    Depends(require_active_workspace_membership),
]


def require_workspace_owner(
    access: ActiveWorkspaceMembership,
) -> WorkspaceAccess:
    try:
        return require_owner_access(access)
    except WorkspaceOwnerRequiredError as error:
        raise V2APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="WORKSPACE_OWNER_REQUIRED",
            message="Se requiere ser propietario del espacio de trabajo.",
        ) from error


WorkspaceOwner = Annotated[WorkspaceAccess, Depends(require_workspace_owner)]
