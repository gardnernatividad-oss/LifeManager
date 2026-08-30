import uuid

from fastapi import APIRouter, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceAppearanceUpdate, WorkspaceRead, WorkspaceSummaryRead
from app.services.v2_workspace import (
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
    WorkspaceInvariantError,
    create_shared_workspace,
    list_active_workspaces,
    list_manageable_workspaces,
    update_workspace_appearance,
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
        color=workspace.color or ("GREEN" if workspace.kind.value == "PERSONAL" else "BLUE"),
        icon=workspace.icon or ("HOME" if workspace.kind.value == "PERSONAL" else "USERS"),
        lock_version=workspace.lock_version or 1,
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
        color=workspace.color or "BLUE",
        icon=workspace.icon or "USERS",
        lock_version=workspace.lock_version or 1,
    )


@router.patch("/{workspace_id}/appearance", response_model=WorkspaceSummaryRead)
def update_appearance(
    workspace_id: uuid.UUID,
    appearance_in: WorkspaceAppearanceUpdate,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceSummaryRead:
    try:
        workspace = update_workspace_appearance(
            db,
            account=current_account,
            workspace_id=workspace_id,
            appearance_in=appearance_in,
        )
        db.commit()
        db.refresh(workspace)
    except WorkspaceAccessNotFoundError as error:
        db.rollback()
        raise V2APIError(status_code=404, code="WORKSPACE_NOT_FOUND", message="No se encontró el espacio de trabajo.") from error
    except WorkspaceInvariantError as error:
        db.rollback()
        raise V2APIError(status_code=409, code="WORKSPACE_CONFLICT", message="El espacio cambió. Actualiza e intenta nuevamente.") from error
    except Exception:
        db.rollback()
        raise
    access = next(
        item for item in list_active_workspaces(db, account=current_account)
        if item.workspace.id == workspace.id
    )
    return _summary(db, access, timezone=current_account.timezone)
