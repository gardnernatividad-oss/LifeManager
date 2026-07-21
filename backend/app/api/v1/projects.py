import uuid

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import project_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects",
    tags=["Projects"],
)


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, project_service.ProjectNotFoundError):
        raise HTTPException(status_code=404, detail="Project not found") from error
    if isinstance(error, project_service.ProjectNameConflictError):
        raise HTTPException(status_code=409, detail="Project name already exists") from error
    raise HTTPException(status_code=403, detail=str(error)) from error


def _commit_project_write(
    db: Session,
    operation: Callable[..., Project],
    **kwargs: object,
) -> ProjectRead:
    try:
        project = operation(db, **kwargs)
        db.commit()
        db.refresh(project)
    except (
        project_service.ProjectNotFoundError,
        project_service.ProjectPermissionError,
        project_service.ProjectNameConflictError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return ProjectRead.model_validate(project)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    workspace_id: uuid.UUID,
    project_in: ProjectCreate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> ProjectRead:
    return _commit_project_write(
        db,
        project_service.create_project,
        workspace_id=workspace_id,
        current_user=current_user,
        project_in=project_in,
    )


@router.get("", response_model=list[ProjectRead])
def list_projects(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    active: bool | None = Query(default=None),
) -> list[ProjectRead]:
    try:
        projects = project_service.list_projects(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            active=active,
        )
    except project_service.ProjectPermissionError as error:
        _raise_http_error(error)
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> ProjectRead:
    try:
        project = project_service.get_project(
            db,
            workspace_id=workspace_id,
            project_id=project_id,
            current_user=current_user,
        )
    except (project_service.ProjectNotFoundError, project_service.ProjectPermissionError) as error:
        _raise_http_error(error)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> ProjectRead:
    return _commit_project_write(
        db,
        project_service.update_project,
        workspace_id=workspace_id,
        project_id=project_id,
        current_user=current_user,
        project_in=project_in,
    )


@router.post("/{project_id}/activate", response_model=ProjectRead)
def activate_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> ProjectRead:
    return _commit_project_write(
        db,
        project_service.activate_project,
        workspace_id=workspace_id,
        project_id=project_id,
        current_user=current_user,
    )


@router.post("/{project_id}/deactivate", response_model=ProjectRead)
def deactivate_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> ProjectRead:
    return _commit_project_write(
        db,
        project_service.deactivate_project,
        workspace_id=workspace_id,
        project_id=project_id,
        current_user=current_user,
    )
