import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.v2.dependencies import SessionDependency, UsableAccount, WorkspaceOwner
from app.api.v2.errors import V2APIError
from app.models import Workspace
from app.schemas.v2_workspace_invitation import (
    WorkspaceInvitationCreate,
    WorkspaceInvitationRead,
)
from app.services.v2_workspace_invitation import (
    WorkspaceInvitationConflictError,
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTargetError,
    accept_workspace_invitation,
    cancel_workspace_invitation,
    create_workspace_invitation,
    list_current_user_invitations,
    list_workspace_invitations,
    reject_workspace_invitation,
)


router = APIRouter(tags=["V2 Workspace Invitations"])


def _read(invitation, workspace_name: str) -> WorkspaceInvitationRead:
    return WorkspaceInvitationRead(
        id=invitation.id,
        workspace_id=invitation.workspace_id,
        workspace_name=workspace_name,
        recipient_email=invitation.recipient_email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


def _raise_domain_error(error: ValueError) -> None:
    if isinstance(error, WorkspaceInvitationNotFoundError):
        raise V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INVITATION_NOT_FOUND",
            message="No se encontró la invitación.",
        ) from error
    if isinstance(error, WorkspaceInvitationTargetError):
        raise V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INVITATION_TARGET_NOT_FOUND",
            message="No se encontró una cuenta disponible para invitar.",
        ) from error
    raise V2APIError(
        status_code=status.HTTP_409_CONFLICT,
        code="INVITATION_CONFLICT",
        message="La invitación no está disponible para esta acción.",
    ) from error


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=WorkspaceInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    workspace_id: uuid.UUID,
    invitation_in: WorkspaceInvitationCreate,
    db: SessionDependency,
    owner_access: WorkspaceOwner,
) -> WorkspaceInvitationRead:
    del workspace_id
    try:
        invitation = create_workspace_invitation(
            db, owner_access=owner_access, invitation_in=invitation_in
        )
        db.commit()
        db.refresh(invitation)
    except (WorkspaceInvitationConflictError, WorkspaceInvitationTargetError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(invitation, owner_access.workspace.name)


@router.get(
    "/workspaces/{workspace_id}/invitations",
    response_model=list[WorkspaceInvitationRead],
)
def list_workspace_pending_invitations(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    owner_access: WorkspaceOwner,
) -> list[WorkspaceInvitationRead]:
    del workspace_id
    try:
        rows = list_workspace_invitations(db, owner_access=owner_access)
    except WorkspaceInvitationConflictError as error:
        _raise_domain_error(error)
    return [_read(invitation, workspace_name) for invitation, workspace_name in rows]


@router.get(
    "/workspace-invitations",
    response_model=list[WorkspaceInvitationRead],
)
def list_my_pending_invitations(
    db: SessionDependency,
    current_account: UsableAccount,
) -> list[WorkspaceInvitationRead]:
    return [
        _read(invitation, workspace_name)
        for invitation, workspace_name in list_current_user_invitations(
            db, recipient=current_account
        )
    ]


def _recipient_action(
    *,
    action,
    invitation_id: uuid.UUID,
    db,
    current_account,
) -> WorkspaceInvitationRead:
    try:
        invitation = action(
            db, invitation_id=invitation_id, recipient=current_account
        )
        workspace_name = db.scalar(
            select(Workspace.name).where(Workspace.id == invitation.workspace_id)
        )
        db.commit()
        db.refresh(invitation)
    except (WorkspaceInvitationNotFoundError, WorkspaceInvitationConflictError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(invitation, workspace_name)


@router.post(
    "/workspace-invitations/{invitation_id}/accept",
    response_model=WorkspaceInvitationRead,
)
def accept_invitation(
    invitation_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceInvitationRead:
    return _recipient_action(
        action=accept_workspace_invitation,
        invitation_id=invitation_id,
        db=db,
        current_account=current_account,
    )


@router.post(
    "/workspace-invitations/{invitation_id}/reject",
    response_model=WorkspaceInvitationRead,
)
def reject_invitation(
    invitation_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceInvitationRead:
    return _recipient_action(
        action=reject_workspace_invitation,
        invitation_id=invitation_id,
        db=db,
        current_account=current_account,
    )


@router.post(
    "/workspace-invitations/{invitation_id}/cancel",
    response_model=WorkspaceInvitationRead,
)
def cancel_invitation(
    invitation_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceInvitationRead:
    try:
        invitation = cancel_workspace_invitation(
            db,
            invitation_id=invitation_id,
            owner=current_account,
        )
        workspace_name = db.scalar(
            select(Workspace.name).where(Workspace.id == invitation.workspace_id)
        )
        db.commit()
        db.refresh(invitation)
    except (WorkspaceInvitationNotFoundError, WorkspaceInvitationConflictError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(invitation, workspace_name)
