import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.workspace import get_workspace_membership
from app.services.task_resolution_service import TaskAlreadyResolved


class TaskNotFoundError(LookupError):
    pass


class TaskPermissionError(PermissionError):
    pass


class TaskCategoryNotFoundError(LookupError):
    pass


class TaskCategoryInactiveError(ValueError):
    pass


class TaskProjectNotFoundError(LookupError):
    pass


class TaskProjectInactiveError(ValueError):
    pass


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
        raise TaskPermissionError("Workspace access denied")
    return membership


def _get_scoped_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> Task:
    statement = select(Task).where(
        Task.id == task_id,
        Task.workspace_id == workspace_id,
    )
    task = db.scalar(statement)
    if task is None:
        raise TaskNotFoundError("Task not found")
    return task


def _resolve_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    require_active: bool,
) -> Category:
    statement = select(Category).where(
        Category.id == category_id,
        Category.workspace_id == workspace_id,
    )
    category = db.scalar(statement)
    if category is None:
        raise TaskCategoryNotFoundError("Category not found")
    if require_active and not category.is_active:
        raise TaskCategoryInactiveError("Category is inactive")
    return category


def _resolve_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    require_active: bool,
) -> Project:
    statement = select(Project).where(
        Project.id == project_id,
        Project.workspace_id == workspace_id,
    )
    project = db.scalar(statement)
    if project is None:
        raise TaskProjectNotFoundError("Project not found")
    if require_active and not project.is_active:
        raise TaskProjectInactiveError("Project is inactive")
    return project


def create_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    task_in: TaskCreate,
) -> Task:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    task_data = task_in.model_dump()
    category_id = task_data.pop("category_id")
    project_id = task_data.pop("project_id")
    if category_id is not None:
        _resolve_category(
            db,
            workspace_id=workspace_id,
            category_id=category_id,
            require_active=True,
        )
    if project_id is not None:
        _resolve_project(
            db,
            workspace_id=workspace_id,
            project_id=project_id,
            require_active=True,
        )
    task = Task(
        workspace_id=workspace_id,
        created_by_id=current_user.id,
        category_id=category_id,
        project_id=project_id,
        outcome=None,
        resolved_at=None,
        **task_data,
    )
    db.add(task)
    db.flush()
    return task


def list_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    category_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> tuple[list[Task], int]:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    filters: list[object] = [Task.workspace_id == workspace_id]
    if category_id is not None:
        _resolve_category(
            db,
            workspace_id=workspace_id,
            category_id=category_id,
            require_active=False,
        )
        filters.append(Task.category_id == category_id)
    if project_id is not None:
        _resolve_project(
            db,
            workspace_id=workspace_id,
            project_id=project_id,
            require_active=False,
        )
        filters.append(Task.project_id == project_id)
    statement = (
        select(Task)
        .where(*filters)
        .order_by(Task.scheduled_at, Task.created_at, Task.id)
    )
    count_statement = select(func.count()).select_from(Task).where(*filters)

    tasks = list(db.scalars(statement).all())
    total = db.scalar(count_statement)
    return tasks, int(total or 0)


def get_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> Task:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    return _get_scoped_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
    )


def update_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
    task_in: TaskUpdate,
) -> Task:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    task = _get_scoped_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    changes = task_in.model_dump(exclude_unset=True)
    if task.outcome is not None and changes:
        raise TaskAlreadyResolved("Task is already resolved")
    if "category_id" in changes:
        category_id = changes.pop("category_id")
        if category_id is not None:
            _resolve_category(
                db,
                workspace_id=workspace_id,
                category_id=category_id,
                require_active=True,
            )
        task.category_id = category_id
    if "project_id" in changes:
        project_id = changes.pop("project_id")
        if project_id is not None:
            _resolve_project(
                db,
                workspace_id=workspace_id,
                project_id=project_id,
                require_active=True,
            )
        task.project_id = project_id
    if "scheduled_at" in changes:
        scheduled_at = changes.pop("scheduled_at")
        task.scheduled_at = scheduled_at
    for field, value in changes.items():
        setattr(task, field, value)

    db.flush()
    return task
