import math
import uuid

from fastapi import APIRouter, Query, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.models import Project
from app.schemas.v2_project import ProjectCreate, ProjectListResponse, ProjectRead, ProjectUpdate, ProjectVersion
from app.services.v2_project import ProjectConflictError, ProjectNotFoundError, ProjectReferenceUnavailableError, create_project, deactivate_project, get_project, list_projects, project_projection, reactivate_project, update_project


router = APIRouter(prefix="/workspaces/{workspace_id}/projects", tags=["V2 Projects"])


def _raise(error: Exception) -> None:
    if isinstance(error, (ProjectNotFoundError, ProjectReferenceUnavailableError)):
        code = "PROJECT_NOT_FOUND" if isinstance(error, ProjectNotFoundError) else "PROJECT_REFERENCE_UNAVAILABLE"
        raise V2APIError(status_code=404, code=code, message="No se encontró el Proyecto o una referencia disponible.") from error
    raise V2APIError(status_code=409, code="PROJECT_CONFLICT", message="El Proyecto cambió o no admite esta acción.") from error


def _read(db: SessionDependency, project: Project, *, category=None, leader=None) -> ProjectRead:
    category, leader = project_projection(db, project=project, category=category, leader=leader)
    return ProjectRead(
        id=project.id, workspace_id=project.workspace_id, category_id=project.category_id, category_name=category.name,
        leader_user_id=project.leader_user_id, leader_display_name=f"{leader.first_name} {leader.last_name}".strip(), leader_email=leader.email,
        name=project.name, description=project.description, is_active=project.is_active,
        planned_date=None, progress=None, state=None, compliance=None, compliance_detail_days=None, completion_date=None,
        lock_version=project.lock_version, can_edit=True, can_deactivate=project.is_active, can_reactivate=not project.is_active,
        created_at=project.created_at, updated_at=project.updated_at,
    )


def _write(db: SessionDependency, operation):
    try:
        result = operation()
        db.commit()
        db.refresh(result)
        return result
    except (ProjectNotFoundError, ProjectConflictError, ProjectReferenceUnavailableError) as error:
        db.rollback()
        _raise(error)
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create(workspace_id: uuid.UUID, project_in: ProjectCreate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectRead:
    del workspace_id
    return _read(db, _write(db, lambda: create_project(db, access=access, actor=account, project_in=project_in)))


@router.get("", response_model=ProjectListResponse)
def index(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), is_active: bool | None = None, category_id: uuid.UUID | None = None, leader_user_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=255)) -> ProjectListResponse:
    del account, access
    try:
        rows, total = list_projects(db, workspace_id=workspace_id, page=page, page_size=page_size, is_active=is_active, category_id=category_id, leader_user_id=leader_user_id, search=search.strip() if search else None)
    except ProjectReferenceUnavailableError as error:
        _raise(error)
    return ProjectListResponse(items=[_read(db, project, category=category, leader=leader) for project, category, leader in rows], total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size))


@router.get("/{project_id}", response_model=ProjectRead)
def detail(workspace_id: uuid.UUID, project_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectRead:
    del account, access
    try:
        return _read(db, get_project(db, workspace_id=workspace_id, project_id=project_id))
    except ProjectNotFoundError as error:
        _raise(error)


@router.patch("/{project_id}", response_model=ProjectRead)
def patch(workspace_id: uuid.UUID, project_id: uuid.UUID, project_in: ProjectUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectRead:
    del workspace_id
    return _read(db, _write(db, lambda: update_project(db, access=access, actor=account, project_id=project_id, project_in=project_in)))


@router.post("/{project_id}/deactivate", response_model=ProjectRead)
def deactivate(workspace_id: uuid.UUID, project_id: uuid.UUID, project_in: ProjectVersion, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectRead:
    del workspace_id, account
    return _read(db, _write(db, lambda: deactivate_project(db, access=access, project_id=project_id, expected_version=project_in.lock_version)))


@router.post("/{project_id}/reactivate", response_model=ProjectRead)
def reactivate(workspace_id: uuid.UUID, project_id: uuid.UUID, project_in: ProjectVersion, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectRead:
    del workspace_id, account
    return _read(db, _write(db, lambda: reactivate_project(db, access=access, project_id=project_id, expected_version=project_in.lock_version)))
