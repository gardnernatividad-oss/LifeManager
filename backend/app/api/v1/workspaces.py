import uuid

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace_member import WorkspaceMember, WorkspaceRole
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.services import workspace as workspace_service

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDependency = Annotated[Session, Depends(get_db)]


def get_membership_or_403(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember:
    membership = workspace_service.get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace access denied",
        )
    return membership


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    workspace_in: WorkspaceCreate,
    db: SessionDependency,
    user_id: uuid.UUID,
) -> WorkspaceRead:
    owner = db.get(User, user_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        workspace = workspace_service.create_workspace(
            db,
            owner=owner,
            workspace_in=workspace_in,
        )
        db.commit()
        db.refresh(workspace)
    except Exception:
        db.rollback()
        raise

    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    db: SessionDependency,
    user_id: uuid.UUID,
) -> list[WorkspaceRead]:
    workspaces = workspace_service.list_user_workspaces(db, user_id=user_id)
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    user_id: uuid.UUID,
) -> WorkspaceRead:
    workspace = workspace_service.get_workspace(db, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    get_membership_or_403(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    return WorkspaceRead.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: uuid.UUID,
    workspace_in: WorkspaceUpdate,
    db: SessionDependency,
    user_id: uuid.UUID,
) -> WorkspaceRead:
    workspace = workspace_service.get_workspace(db, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    membership = get_membership_or_403(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership.role not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permissions",
        )

    try:
        workspace = workspace_service.update_workspace(
            db,
            workspace=workspace,
            workspace_in=workspace_in,
        )
        db.commit()
        db.refresh(workspace)
    except Exception:
        db.rollback()
        raise

    return WorkspaceRead.model_validate(workspace)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    user_id: uuid.UUID,
) -> Response:
    workspace = workspace_service.get_workspace(db, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    membership = get_membership_or_403(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership.role is not WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permissions",
        )

    try:
        workspace_service.delete_workspace(db, workspace=workspace)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
