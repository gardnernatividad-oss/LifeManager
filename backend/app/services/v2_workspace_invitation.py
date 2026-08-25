import hashlib
import secrets
import uuid

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceInvitation, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    InvitationStatus,
    MembershipStatus,
    WorkspaceKind,
)
from app.schemas.v2_workspace_invitation import WorkspaceInvitationCreate
from app.services.v2_workspace import WorkspaceAccess


INVITATION_LIFETIME = timedelta(days=14)
_PENDING_INVITATION_CONSTRAINT = "uq_workspace_invitations_pending_email"


class WorkspaceInvitationNotFoundError(ValueError):
    pass


class WorkspaceInvitationConflictError(ValueError):
    pass


class WorkspaceInvitationTargetError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_pending_conflict(error: IntegrityError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    return (
        getattr(diagnostic, "constraint_name", None)
        == _PENDING_INVITATION_CONSTRAINT
    )


def _new_token_digest() -> bytes:
    raw_token = secrets.token_bytes(32)
    return hashlib.sha256(raw_token).digest()


def _require_shared(workspace: Workspace) -> None:
    if workspace.kind != WorkspaceKind.SHARED:
        raise WorkspaceInvitationConflictError(
            "Personal workspace does not support invitations"
        )


def _expire_existing_pending(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    recipient_email: str,
    now: datetime,
) -> None:
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.recipient_email == recipient_email,
            WorkspaceInvitation.status == InvitationStatus.PENDING,
        )
        .with_for_update()
    )
    if invitation is None:
        return
    if invitation.expires_at > now:
        raise WorkspaceInvitationConflictError("Invitation already pending")
    invitation.status = InvitationStatus.EXPIRED
    invitation.responded_at = now
    db.flush()


def create_workspace_invitation(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
    invitation_in: WorkspaceInvitationCreate,
    now: datetime | None = None,
) -> WorkspaceInvitation:
    _require_shared(owner_access.workspace)
    current_time = now or _now()
    normalized_email = str(invitation_in.email).strip().lower()
    recipient = db.scalar(
        select(User)
        .where(
            User.email == normalized_email,
            User.account_status == AccountStatus.ACTIVE,
        )
        .with_for_update()
    )
    if recipient is None:
        raise WorkspaceInvitationTargetError("Eligible account not found")
    if recipient.id == owner_access.workspace.owner_user_id:
        raise WorkspaceInvitationConflictError("Workspace owner cannot be invited")

    membership = db.scalar(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == owner_access.workspace.id,
            WorkspaceMember.user_id == recipient.id,
        )
        .with_for_update()
    )
    if membership is not None and membership.status == MembershipStatus.ACTIVE:
        raise WorkspaceInvitationConflictError("User is already an active member")

    _expire_existing_pending(
        db,
        workspace_id=owner_access.workspace.id,
        recipient_email=normalized_email,
        now=current_time,
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=owner_access.workspace.id,
        recipient_email=normalized_email,
        recipient_user_id=recipient.id,
        inviter_user_id=owner_access.membership.user_id,
        status=InvitationStatus.PENDING,
        token_digest=_new_token_digest(),
        expires_at=current_time + INVITATION_LIFETIME,
        created_at=current_time,
    )
    db.add(invitation)
    try:
        db.flush()
    except IntegrityError as error:
        if _is_pending_conflict(error):
            raise WorkspaceInvitationConflictError(
                "Invitation already pending"
            ) from error
        raise
    return invitation


def list_workspace_invitations(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
    now: datetime | None = None,
) -> list[tuple[WorkspaceInvitation, str]]:
    _require_shared(owner_access.workspace)
    current_time = now or _now()
    invitations = list(
        db.scalars(
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == owner_access.workspace.id,
                WorkspaceInvitation.status == InvitationStatus.PENDING,
                WorkspaceInvitation.expires_at > current_time,
            )
            .order_by(
                WorkspaceInvitation.created_at.desc(),
                WorkspaceInvitation.id,
            )
        ).all()
    )
    return [(invitation, owner_access.workspace.name) for invitation in invitations]


def list_current_user_invitations(
    db: Session,
    *,
    recipient: User,
    now: datetime | None = None,
) -> list[tuple[WorkspaceInvitation, str]]:
    current_time = now or _now()
    rows = db.execute(
        select(WorkspaceInvitation, Workspace.name)
        .join(Workspace, Workspace.id == WorkspaceInvitation.workspace_id)
        .where(
            WorkspaceInvitation.recipient_user_id == recipient.id,
            WorkspaceInvitation.status == InvitationStatus.PENDING,
            WorkspaceInvitation.expires_at > current_time,
            Workspace.kind == WorkspaceKind.SHARED,
        )
        .order_by(
            WorkspaceInvitation.created_at.desc(),
            WorkspaceInvitation.id,
        )
    ).all()
    return [(invitation, workspace_name) for invitation, workspace_name in rows]


def _lock_recipient_invitation(
    db: Session,
    *,
    invitation_id: uuid.UUID,
    recipient: User,
    now: datetime,
) -> WorkspaceInvitation:
    if recipient.account_status != AccountStatus.ACTIVE:
        raise WorkspaceInvitationNotFoundError("Invitation not found")
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.recipient_user_id == recipient.id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise WorkspaceInvitationNotFoundError("Invitation not found")
    if invitation.status != InvitationStatus.PENDING or invitation.expires_at <= now:
        raise WorkspaceInvitationConflictError("Invitation is not actionable")
    return invitation


def accept_workspace_invitation(
    db: Session,
    *,
    invitation_id: uuid.UUID,
    recipient: User,
    now: datetime | None = None,
) -> WorkspaceInvitation:
    current_time = now or _now()
    invitation = _lock_recipient_invitation(
        db, invitation_id=invitation_id, recipient=recipient, now=current_time
    )
    workspace = db.scalar(
        select(Workspace)
        .where(Workspace.id == invitation.workspace_id)
        .with_for_update()
    )
    if workspace is None:
        raise WorkspaceInvitationNotFoundError("Invitation not found")
    _require_shared(workspace)
    membership = db.scalar(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == recipient.id,
        )
        .with_for_update()
    )
    if membership is None:
        membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=recipient.id,
            status=MembershipStatus.ACTIVE,
            calendar_visibility=CalendarVisibility.HIDE,
            joined_at=current_time,
        )
        db.add(membership)
    elif membership.status in {MembershipStatus.LEFT, MembershipStatus.REMOVED}:
        membership.status = MembershipStatus.ACTIVE
        membership.joined_at = current_time
        membership.ended_at = None
        membership.calendar_visibility = CalendarVisibility.HIDE
        membership.lock_version += 1
    else:
        raise WorkspaceInvitationConflictError("User is already an active member")
    invitation.status = InvitationStatus.ACCEPTED
    invitation.responded_at = current_time
    db.flush()
    return invitation


def reject_workspace_invitation(
    db: Session,
    *,
    invitation_id: uuid.UUID,
    recipient: User,
    now: datetime | None = None,
) -> WorkspaceInvitation:
    current_time = now or _now()
    invitation = _lock_recipient_invitation(
        db, invitation_id=invitation_id, recipient=recipient, now=current_time
    )
    invitation.status = InvitationStatus.REJECTED
    invitation.responded_at = current_time
    db.flush()
    return invitation


def cancel_workspace_invitation(
    db: Session,
    *,
    invitation_id: uuid.UUID,
    owner: User,
    now: datetime | None = None,
) -> WorkspaceInvitation:
    current_time = now or _now()
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.id == invitation_id)
        .with_for_update()
    )
    if invitation is None:
        raise WorkspaceInvitationNotFoundError("Invitation not found")
    workspace = db.scalar(
        select(Workspace)
        .where(
            Workspace.id == invitation.workspace_id,
            Workspace.owner_user_id == owner.id,
            Workspace.kind == WorkspaceKind.SHARED,
        )
        .with_for_update()
    )
    if workspace is None:
        raise WorkspaceInvitationNotFoundError("Invitation not found")
    if invitation.status != InvitationStatus.PENDING or invitation.expires_at <= current_time:
        raise WorkspaceInvitationConflictError("Invitation is not actionable")
    invitation.status = InvitationStatus.CANCELLED
    invitation.cancelled_at = current_time
    db.flush()
    return invitation
