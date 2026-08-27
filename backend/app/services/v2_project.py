import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Project, ProjectLeaderHistory, User, WorkspaceMember
from app.models.enums import AccountStatus, MembershipStatus, WorkspaceKind
from app.schemas.v2_project import ProjectCreate, ProjectUpdate
from app.services.v2_workspace import WorkspaceAccess


class ProjectNotFoundError(LookupError):
    pass


class ProjectConflictError(ValueError):
    pass


class ProjectReferenceUnavailableError(ValueError):
    pass


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint in {
            "fk_projects_category_workspace",
            "fk_projects_leader_membership",
            "fk_projects_creator_membership",
            "fk_project_leader_history_leader_membership",
            "fk_project_leader_history_actor_membership",
        }:
            raise ProjectReferenceUnavailableError("Project reference unavailable") from error
        raise


def _category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.workspace_id == workspace_id).with_for_update())
    if category is None or not category.is_active:
        raise ProjectReferenceUnavailableError("Category unavailable")
    return category


def _leader(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> User:
    row = db.execute(
        select(User, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            User.id == user_id,
            User.account_status == AccountStatus.ACTIVE,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise ProjectReferenceUnavailableError("Leader unavailable")
    return row[0]


def _project(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, lock: bool = False) -> Project:
    statement = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise ProjectNotFoundError("Project not found")
    return project


def _check_version(project: Project, expected: int) -> None:
    if project.lock_version != expected:
        raise ProjectConflictError("Project version conflict")


def create_project(db: Session, *, access: WorkspaceAccess, actor: User, project_in: ProjectCreate) -> Project:
    _category(db, workspace_id=access.workspace.id, category_id=project_in.category_id)
    leader_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (project_in.leader_user_id or actor.id)
    _leader(db, workspace_id=access.workspace.id, user_id=leader_id)
    project = Project(
        workspace_id=access.workspace.id,
        category_id=project_in.category_id,
        leader_user_id=leader_id,
        name=project_in.name,
        description=project_in.description,
        is_active=True,
        created_by_user_id=actor.id,
    )
    db.add(project)
    _flush(db)
    db.add(ProjectLeaderHistory(project_id=project.id, workspace_id=project.workspace_id, leader_user_id=leader_id, actor_user_id=actor.id))
    _flush(db)
    return project


def list_projects(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    is_active: bool | None = None,
    category_id: uuid.UUID | None = None,
    leader_user_id: uuid.UUID | None = None,
    search: str | None = None,
) -> tuple[list[tuple[Project, Category, User]], int]:
    if category_id is not None and db.scalar(select(Category.id).where(Category.id == category_id, Category.workspace_id == workspace_id)) is None:
        raise ProjectReferenceUnavailableError("Category unavailable")
    if leader_user_id is not None and db.scalar(select(WorkspaceMember.user_id).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == leader_user_id)) is None:
        raise ProjectReferenceUnavailableError("Leader unavailable")
    filters = [Project.workspace_id == workspace_id]
    if is_active is not None:
        filters.append(Project.is_active.is_(is_active))
    if category_id is not None:
        filters.append(Project.category_id == category_id)
    if leader_user_id is not None:
        filters.append(Project.leader_user_id == leader_user_id)
    if search:
        filters.append(Project.name.icontains(search, autoescape=True))
    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    rows = list(
        db.execute(
            select(Project, Category, User)
            .join(Category, and_(Category.id == Project.category_id, Category.workspace_id == Project.workspace_id))
            .join(User, User.id == Project.leader_user_id)
            .where(*filters)
            .order_by(Project.is_active.desc(), Project.name, Project.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return rows, int(total)


def get_project(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    return _project(db, workspace_id=workspace_id, project_id=project_id)


def update_project(db: Session, *, access: WorkspaceAccess, actor: User, project_id: uuid.UUID, project_in: ProjectUpdate) -> Project:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_version(project, project_in.lock_version)
    values = project_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    if "category_id" in values and values["category_id"] != project.category_id:
        _category(db, workspace_id=access.workspace.id, category_id=values["category_id"])
    leader_changed = "leader_user_id" in values and values["leader_user_id"] != project.leader_user_id
    if leader_changed:
        _leader(db, workspace_id=access.workspace.id, user_id=values["leader_user_id"])
    for field, value in values.items():
        setattr(project, field, value)
    project.lock_version += 1
    if leader_changed:
        db.add(ProjectLeaderHistory(project_id=project.id, workspace_id=project.workspace_id, leader_user_id=project.leader_user_id, actor_user_id=actor.id))
    _flush(db)
    return project


def deactivate_project(db: Session, *, access: WorkspaceAccess, project_id: uuid.UUID, expected_version: int) -> Project:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_version(project, expected_version)
    if not project.is_active:
        raise ProjectConflictError("Project is already inactive")
    project.is_active = False
    project.lock_version += 1
    _flush(db)
    return project


def reactivate_project(db: Session, *, access: WorkspaceAccess, project_id: uuid.UUID, expected_version: int) -> Project:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_version(project, expected_version)
    if project.is_active:
        raise ProjectConflictError("Project is already active")
    project.is_active = True
    project.lock_version += 1
    _flush(db)
    return project


def project_projection(db: Session, *, project: Project, category: Category | None = None, leader: User | None = None) -> tuple[Category, User]:
    category = category or db.scalar(select(Category).where(Category.id == project.category_id, Category.workspace_id == project.workspace_id))
    leader = leader or db.scalar(select(User).where(User.id == project.leader_user_id))
    if category is None or leader is None:
        raise ProjectNotFoundError("Project not found")
    return category, leader
