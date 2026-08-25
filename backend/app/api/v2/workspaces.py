from fastapi import APIRouter, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceRead
from app.services.v2_workspace import create_shared_workspace


router = APIRouter(prefix="/workspaces", tags=["V2 Workspaces"])


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
