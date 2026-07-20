import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


def create_workspace(
    db: Session,
    *,
    owner: User,
    workspace_in: WorkspaceCreate,
) -> Workspace:
    workspace = Workspace(**workspace_in.model_dump())
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        user=owner,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )
    db.add(membership)

    return workspace


def get_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> Workspace | None:
    statement = select(Workspace).where(Workspace.id == workspace_id)
    return db.scalar(statement)


def get_workspace_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    statement = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
    )
    return db.scalar(statement)


def list_user_workspaces(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[Workspace]:
    statement = (
        select(Workspace)
        .join(WorkspaceMember)
        .where(WorkspaceMember.user_id == user_id)
        .distinct()
        .order_by(Workspace.created_at, Workspace.id)
    )
    return list(db.scalars(statement).all())


def update_workspace(
    db: Session,
    *,
    workspace: Workspace,
    workspace_in: WorkspaceUpdate,
) -> Workspace:
    for field, value in workspace_in.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)

    db.flush()
    return workspace


def delete_workspace(
    db: Session,
    *,
    workspace: Workspace,
) -> None:
    db.delete(workspace)
    db.flush()
