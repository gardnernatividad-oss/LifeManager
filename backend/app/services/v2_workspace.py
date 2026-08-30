import uuid

from dataclasses import dataclass

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceAppearanceUpdate


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
        color="BLUE",
        icon="USERS",
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


def update_workspace_appearance(
    db: Session,
    *,
    account: User,
    workspace_id: uuid.UUID,
    appearance_in: WorkspaceAppearanceUpdate,
) -> Workspace:
    row = db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            WorkspaceMember.user_id == account.id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .with_for_update(of=Workspace)
    ).one_or_none()
    if row is None:
        raise WorkspaceAccessNotFoundError("Workspace not found")
    workspace, _membership = row
    if workspace.lock_version != appearance_in.lock_version:
        raise WorkspaceInvariantError("Stale workspace version")
    workspace.color = appearance_in.color
    workspace.icon = appearance_in.icon
    workspace.lock_version += 1
    db.flush()
    return workspace


def list_active_workspaces(
    db: Session,
    *,
    account: User,
) -> list[WorkspaceAccess]:
    """List operational Workspaces visible through an ACTIVE membership."""
    if account.account_status != AccountStatus.ACTIVE:
        return []
    personal_first = case((Workspace.kind == WorkspaceKind.PERSONAL, 0), else_=1)
    rows = db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == account.id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
        )
        .order_by(
            personal_first,
            Workspace.name,
            Workspace.id,
        )
    ).all()
    return [WorkspaceAccess(workspace=workspace, membership=membership) for workspace, membership in rows]


def list_manageable_workspaces(
    db: Session,
    *,
    account: User,
) -> list[WorkspaceAccess]:
    """List active memberships plus owner-visible inactive Shared Workspaces."""
    if account.account_status != AccountStatus.ACTIVE:
        return []
    personal_first = case((Workspace.kind == WorkspaceKind.PERSONAL, 0), else_=1)
    rows = db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == account.id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            (
                (Workspace.lifecycle == WorkspaceLifecycle.ACTIVE)
                | (
                    (Workspace.lifecycle == WorkspaceLifecycle.INACTIVE)
                    & (Workspace.owner_user_id == account.id)
                )
            ),
        )
        .order_by(
            personal_first,
            Workspace.lifecycle,
            Workspace.name,
            Workspace.id,
        )
    ).all()
    return [WorkspaceAccess(workspace=workspace, membership=membership) for workspace, membership in rows]


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
