import uuid

from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import MembershipStatus, WorkspaceKind
from app.services.v2_workspace import WorkspaceAccess


class WorkspaceMemberNotFoundError(ValueError):
    pass


class WorkspaceMemberPermissionError(ValueError):
    pass


class WorkspaceMemberConflictError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_shared(workspace: Workspace) -> None:
    if workspace.kind != WorkspaceKind.SHARED:
        raise WorkspaceMemberConflictError(
            "Personal workspace does not support membership management"
        )


def list_workspace_members(
    db: Session,
    *,
    access: WorkspaceAccess,
) -> list[tuple[WorkspaceMember, User]]:
    _require_shared(access.workspace)
    owner_first = case(
        (WorkspaceMember.user_id == access.workspace.owner_user_id, 0),
        else_=1,
    )
    return list(
        db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == access.workspace.id)
            .order_by(
                owner_first,
                User.first_name,
                User.last_name,
                User.email,
                WorkspaceMember.user_id,
            )
        ).all()
    )


def remove_workspace_member(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
    target_user_id: uuid.UUID,
    now: datetime | None = None,
) -> tuple[WorkspaceMember, User]:
    workspace = db.scalar(
        select(Workspace)
        .where(
            Workspace.id == owner_access.workspace.id,
            Workspace.owner_user_id == owner_access.membership.user_id,
        )
        .with_for_update()
    )
    if workspace is None:
        raise WorkspaceMemberPermissionError("Workspace owner required")
    _require_shared(workspace)
    if target_user_id == workspace.owner_user_id:
        raise WorkspaceMemberConflictError("Workspace owner cannot be removed")

    row = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None:
        raise WorkspaceMemberNotFoundError("Workspace member not found")
    membership, user = row
    if membership.status != MembershipStatus.ACTIVE:
        raise WorkspaceMemberConflictError("Workspace member is not active")

    membership.status = MembershipStatus.REMOVED
    membership.ended_at = now or _now()
    membership.lock_version += 1
    db.flush()
    return membership, user


def leave_shared_workspace(
    db: Session,
    *,
    access: WorkspaceAccess,
    account: User,
    now: datetime | None = None,
) -> WorkspaceMember:
    workspace = db.scalar(
        select(Workspace)
        .where(
            Workspace.id == access.workspace.id,
        )
        .with_for_update()
    )
    if workspace is None:
        raise WorkspaceMemberNotFoundError("Workspace not found")
    _require_shared(workspace)
    if account.id == workspace.owner_user_id:
        raise WorkspaceMemberConflictError(
            "Workspace ownership must be transferred before leaving"
        )

    membership = db.scalar(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == account.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if membership is None:
        raise WorkspaceMemberNotFoundError("Workspace member not found")
    if membership.status != MembershipStatus.ACTIVE:
        raise WorkspaceMemberConflictError("Workspace member is not active")

    membership.status = MembershipStatus.LEFT
    membership.ended_at = now or _now()
    membership.lock_version += 1
    db.flush()
    return membership
