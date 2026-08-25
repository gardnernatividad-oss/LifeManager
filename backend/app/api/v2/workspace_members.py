import uuid

from fastapi import APIRouter, status

from app.api.v2.dependencies import (
    ActiveWorkspaceMembership,
    SessionDependency,
    UsableAccount,
    WorkspaceOwner,
)
from app.api.v2.errors import V2APIError
from app.models import User, WorkspaceMember
from app.schemas.v2_workspace_member import WorkspaceMemberRead
from app.schemas.v2_workspace_lifecycle import MemberExitResolution
from app.services.v2_workspace_member import (
    WorkspaceMemberConflictError,
    WorkspaceMemberNotFoundError,
    WorkspaceMemberPermissionError,
    leave_shared_workspace,
    list_workspace_members,
    remove_workspace_member,
)


router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["V2 Workspace Members"])


def _read(
    membership: WorkspaceMember,
    user: User,
    *,
    owner_user_id: uuid.UUID,
) -> WorkspaceMemberRead:
    return WorkspaceMemberRead(
        user_id=user.id,
        display_name=f"{user.first_name} {user.last_name}".strip(),
        email=user.email,
        role="Propietario" if user.id == owner_user_id else "Miembro",
        status=membership.status,
        joined_at=membership.joined_at,
        ended_at=membership.ended_at,
    )


def _raise_domain_error(error: ValueError) -> None:
    if isinstance(error, WorkspaceMemberNotFoundError):
        raise V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="WORKSPACE_MEMBER_NOT_FOUND",
            message="No se encontró la membresía.",
        ) from error
    if isinstance(error, WorkspaceMemberPermissionError):
        raise V2APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="WORKSPACE_OWNER_REQUIRED",
            message="Se requiere ser propietario del espacio de trabajo.",
        ) from error
    raise V2APIError(
        status_code=status.HTTP_409_CONFLICT,
        code="WORKSPACE_MEMBERSHIP_CONFLICT",
        message="La membresía no está disponible para esta acción.",
    ) from error


@router.get("/members", response_model=list[WorkspaceMemberRead])
def list_members(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    access: ActiveWorkspaceMembership,
) -> list[WorkspaceMemberRead]:
    del workspace_id
    try:
        rows = list_workspace_members(db, access=access)
    except WorkspaceMemberConflictError as error:
        _raise_domain_error(error)
    return [
        _read(
            membership,
            user,
            owner_user_id=access.workspace.owner_user_id,
        )
        for membership, user in rows
    ]


@router.delete(
    "/members/{user_id}",
    response_model=WorkspaceMemberRead,
)
def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: SessionDependency,
    owner_access: WorkspaceOwner,
    resolution: MemberExitResolution | None = None,
) -> WorkspaceMemberRead:
    del workspace_id
    try:
        membership, user = remove_workspace_member(
            db,
            owner_access=owner_access,
            target_user_id=user_id,
            resolution=resolution,
        )
        db.commit()
        db.refresh(membership)
    except (
        WorkspaceMemberConflictError,
        WorkspaceMemberNotFoundError,
        WorkspaceMemberPermissionError,
    ) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(
        membership,
        user,
        owner_user_id=owner_access.workspace.owner_user_id,
    )


@router.post("/leave", response_model=WorkspaceMemberRead)
def leave_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
    access: ActiveWorkspaceMembership,
    resolution: MemberExitResolution | None = None,
) -> WorkspaceMemberRead:
    del workspace_id
    try:
        membership = leave_shared_workspace(
            db,
            access=access,
            account=current_account,
            resolution=resolution,
        )
        db.commit()
        db.refresh(membership)
    except (WorkspaceMemberConflictError, WorkspaceMemberNotFoundError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(
        membership,
        current_account,
        owner_user_id=access.workspace.owner_user_id,
    )
