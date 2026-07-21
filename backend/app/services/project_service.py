import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.workspace import get_workspace_membership


class ProjectNotFoundError(LookupError):
    pass


class ProjectPermissionError(PermissionError):
    pass


class ProjectNameConflictError(ValueError):
    pass


def normalize_project_name(name: str) -> tuple[str, str]:
    cleaned_name = unicodedata.normalize("NFC", " ".join(name.split()))
    if not cleaned_name:
        raise ValueError("Project name cannot be blank")
    normalized_name = unicodedata.normalize("NFC", cleaned_name.casefold())
    if len(cleaned_name) > 100 or len(normalized_name) > 100:
        raise ValueError("Project name must not exceed 100 characters")
    return cleaned_name, normalized_name


def _require_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership is None:
        raise ProjectPermissionError("Workspace access denied")
    return membership


def _get_scoped_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if project is None:
        raise ProjectNotFoundError("Project not found")
    return project


def _name_exists(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    normalized_name: str,
    exclude_project_id: uuid.UUID | None = None,
) -> bool:
    statement = select(Project.id).where(
        Project.workspace_id == workspace_id,
        Project.normalized_name == normalized_name,
    )
    if exclude_project_id is not None:
        statement = statement.where(Project.id != exclude_project_id)
    return db.scalar(statement) is not None


def _flush_or_raise_name_conflict(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name != "uq_projects_workspace_id_normalized_name":
            raise
        raise ProjectNameConflictError("Project name already exists") from error


def create_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    project_in: ProjectCreate,
) -> Project:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    name, normalized_name = normalize_project_name(project_in.name)
    if _name_exists(db, workspace_id=workspace_id, normalized_name=normalized_name):
        raise ProjectNameConflictError("Project name already exists")
    project = Project(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalized_name,
        description=project_in.description,
        is_active=True,
    )
    db.add(project)
    _flush_or_raise_name_conflict(db)
    return project


def list_projects(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    active: bool | None = None,
) -> list[Project]:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    statement = select(Project).where(Project.workspace_id == workspace_id)
    if active is not None:
        statement = statement.where(Project.is_active.is_(active))
    statement = statement.order_by(Project.normalized_name, Project.name, Project.id)
    return list(db.scalars(statement).all())


def get_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User,
) -> Project:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    return _get_scoped_project(db, workspace_id=workspace_id, project_id=project_id)


def update_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User,
    project_in: ProjectUpdate,
) -> Project:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    project = _get_scoped_project(db, workspace_id=workspace_id, project_id=project_id)
    changes = project_in.model_dump(exclude_unset=True)
    if "name" in changes:
        name, normalized_name = normalize_project_name(changes["name"])
        if normalized_name != project.normalized_name and _name_exists(
            db,
            workspace_id=workspace_id,
            normalized_name=normalized_name,
            exclude_project_id=project.id,
        ):
            raise ProjectNameConflictError("Project name already exists")
        project.name = name
        project.normalized_name = normalized_name
    if "description" in changes:
        project.description = changes["description"]
    _flush_or_raise_name_conflict(db)
    return project


def activate_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User,
) -> Project:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    project = _get_scoped_project(db, workspace_id=workspace_id, project_id=project_id)
    if not project.is_active:
        project.is_active = True
        db.flush()
    return project


def deactivate_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User,
) -> Project:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    project = _get_scoped_project(db, workspace_id=workspace_id, project_id=project_id)
    if project.is_active:
        project.is_active = False
        db.flush()
    return project
