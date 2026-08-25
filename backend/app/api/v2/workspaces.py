from fastapi import APIRouter, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceRead, WorkspaceSummaryRead
from app.services.v2_workspace import (
    WorkspaceAccess,
    create_shared_workspace,
    list_active_workspaces,
    list_manageable_workspaces,
)
from app.services.v2_workspace_lifecycle import workspace_can_be_hard_deleted


router = APIRouter(prefix="/workspaces", tags=["V2 Workspaces"])


def _summary(
    db: SessionDependency,
    access: WorkspaceAccess,
    *,
    timezone: str,
) -> WorkspaceSummaryRead:
    workspace = access.workspace
    is_owner = access.is_owner
    return WorkspaceSummaryRead(
        id=workspace.id,
        name=workspace.name,
        kind=workspace.kind,
        lifecycle=workspace.lifecycle,
        visible_role="Propietario" if is_owner else "Miembro",
        can_manage=is_owner and workspace.kind.value == "SHARED",
        can_delete=(
            is_owner
            and workspace.kind.value == "SHARED"
            and workspace_can_be_hard_deleted(db, workspace=workspace)
        ),
        timezone=timezone,
    )


@router.get("", response_model=list[WorkspaceSummaryRead])
def list_workspaces(
    db: SessionDependency,
    current_account: UsableAccount,
) -> list[WorkspaceSummaryRead]:
    return [
        _summary(db, access, timezone=current_account.timezone)
        for access in list_active_workspaces(db, account=current_account)
    ]


@router.get("/management", response_model=list[WorkspaceSummaryRead])
def list_workspace_management(
    db: SessionDependency,
    current_account: UsableAccount,
) -> list[WorkspaceSummaryRead]:
    return [
        _summary(db, access, timezone=current_account.timezone)
        for access in list_manageable_workspaces(db, account=current_account)
    ]


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    workspace_in: SharedWorkspaceCreate,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceRead:
    try:
        workspace = create_shared_workspace(
            db,
            creator=current_account,
            workspace_in=workspace_in,
        )
        db.commit()
        db.refresh(workspace)
    except Exception:
        db.rollback()
        raise
    return WorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        kind=workspace.kind,
    )
