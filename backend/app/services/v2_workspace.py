import uuid

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace import SharedWorkspaceCreate


class WorkspaceAccessNotFoundError(ValueError):
    pass


class WorkspaceOwnerRequiredError(ValueError):
    pass


class WorkspaceInvariantError(ValueError):
    pass


class PersonalWorkspaceInvariantError(WorkspaceInvariantError):
    pass


@dataclass(frozen=True)
class WorkspaceAccess:
    workspace: Workspace
    membership: WorkspaceMember

    @property
    def is_owner(self) -> bool:
        return self.workspace.owner_user_id == self.membership.user_id


def create_shared_workspace(
    db: Session,
    *,
    creator: User,
    workspace_in: SharedWorkspaceCreate,
) -> Workspace:
    if creator.account_status != AccountStatus.ACTIVE:
        raise WorkspaceAccessNotFoundError("Active account required")

    workspace = Workspace(
        id=uuid.uuid4(),
        name=workspace_in.name,
        kind=WorkspaceKind.SHARED,
        owner_user_id=creator.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=creator.id,
            status=MembershipStatus.ACTIVE,
        )
    )
    db.flush()
    return workspace


def resolve_active_workspace_access(
    db: Session,
    *,
    account: User,
    workspace_id: uuid.UUID,
) -> WorkspaceAccess:
    """Resolve private Workspace access from persisted ACTIVE state only."""
    if account.account_status != AccountStatus.ACTIVE:
        raise WorkspaceAccessNotFoundError("Workspace not found")

    row = db.execute(
        select(Workspace, WorkspaceMember)
        .join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Workspace.id,
        )
        .where(
            Workspace.id == workspace_id,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            WorkspaceMember.user_id == account.id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
    ).one_or_none()
    if row is None:
        raise WorkspaceAccessNotFoundError("Workspace not found")
    workspace, membership = row
    return WorkspaceAccess(workspace=workspace, membership=membership)


def require_workspace_owner(access: WorkspaceAccess) -> WorkspaceAccess:
    if not access.is_owner:
        raise WorkspaceOwnerRequiredError("Workspace owner required")
    return access


def ensure_member_addition_allowed(
    workspace: Workspace,
    *,
    user_id: uuid.UUID,
) -> None:
    if (
        workspace.kind == WorkspaceKind.PERSONAL
        and user_id != workspace.owner_user_id
    ):
        raise PersonalWorkspaceInvariantError(
            "Personal workspace cannot have additional members"
        )


def ensure_membership_can_end(
    workspace: Workspace,
    *,
    user_id: uuid.UUID,
) -> None:
    if user_id == workspace.owner_user_id:
        raise WorkspaceInvariantError(
            "Workspace owner membership cannot end"
        )


def ensure_workspace_can_be_deleted(workspace: Workspace) -> None:
    if workspace.kind == WorkspaceKind.PERSONAL:
        raise PersonalWorkspaceInvariantError(
            "Personal workspace cannot be deleted"
        )


def ensure_workspace_kind_unchanged(
    workspace: Workspace,
    *,
    kind: WorkspaceKind,
) -> None:
    if kind != workspace.kind:
        raise PersonalWorkspaceInvariantError("Workspace kind is immutable")


def ensure_ownership_transfer_allowed(workspace: Workspace) -> None:
    if workspace.kind == WorkspaceKind.PERSONAL:
        raise PersonalWorkspaceInvariantError(
            "Personal workspace ownership cannot be transferred"
        )
