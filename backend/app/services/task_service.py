import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.models.workspace_member import WorkspaceMember, WorkspaceRole
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.workspace import get_workspace_membership


class TaskNotFoundError(LookupError):
    pass


class TaskPermissionError(PermissionError):
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
    task = Task(
        workspace_id=workspace_id,
        created_by_id=current_user.id,
        **task_in.model_dump(),
    )
    db.add(task)
    db.flush()
    return task


def list_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
) -> tuple[list[Task], int]:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    filters = (
        Task.workspace_id == workspace_id,
        Task.is_archived.is_(False),
    )
    statement = (
        select(Task)
        .where(*filters)
        .order_by(Task.position, Task.created_at, Task.id)
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
    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.flush()
    return task


def delete_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> None:
    membership = _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    task = _get_scoped_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    if task.created_by_id != current_user.id and membership.role is not WorkspaceRole.OWNER:
        raise TaskPermissionError("Insufficient task permissions")

    db.delete(task)
    db.flush()
