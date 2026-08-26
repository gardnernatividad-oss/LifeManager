import uuid

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import MasterTask, Task, User, WorkspaceMember
from app.models.enums import AccountStatus, MembershipStatus, TaskResult, WorkspaceKind
from app.schemas.v2_task import TaskCreate, TaskUpdate
from app.services.v2_workspace import WorkspaceAccess


class TaskNotFoundError(LookupError):
    pass


class TaskConflictError(ValueError):
    pass


class TaskPermissionError(ValueError):
    pass


class TaskReferenceUnavailableError(ValueError):
    pass


def _translate_integrity(error: IntegrityError) -> None:
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
    if constraint == "uq_tasks_workspace_master_date_responsible":
        raise TaskConflictError("Task occurrence already exists") from error
    if constraint in {
        "fk_tasks_master_task_workspace",
        "fk_tasks_responsible_membership",
        "fk_tasks_creator_membership",
        "fk_tasks_resolver_membership",
    }:
        raise TaskReferenceUnavailableError("Task reference unavailable") from error
    raise error


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        _translate_integrity(error)


def _master(db: Session, *, workspace_id: uuid.UUID, master_task_id: uuid.UUID, assignable: bool) -> MasterTask:
    statement = select(MasterTask).where(MasterTask.id == master_task_id, MasterTask.workspace_id == workspace_id)
    if assignable:
        statement = statement.with_for_update()
    master = db.scalar(statement)
    if master is None or (assignable and not master.is_active):
        raise TaskReferenceUnavailableError("Task catalog entry unavailable")
    return master


def _responsible(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> User:
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
        raise TaskReferenceUnavailableError("Responsible user unavailable")
    return row[0]


def _task(db: Session, *, workspace_id: uuid.UUID, task_id: uuid.UUID, lock: bool = False) -> Task:
    statement = select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise TaskNotFoundError("Task not found")
    return task


def create_task(db: Session, *, access: WorkspaceAccess, actor: User, task_in: TaskCreate) -> Task:
    _master(db, workspace_id=access.workspace.id, master_task_id=task_in.master_task_id, assignable=True)
    responsible_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (task_in.responsible_user_id or actor.id)
    _responsible(db, workspace_id=access.workspace.id, user_id=responsible_id)
    task = Task(
        workspace_id=access.workspace.id,
        master_task_id=task_in.master_task_id,
        responsible_user_id=responsible_id,
        planned_date=task_in.planned_date,
        created_by_user_id=actor.id,
        generation_batch_id=None,
    )
    db.add(task)
    _flush(db)
    return task


def list_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    planned_from: date | None = None,
    planned_until: date | None = None,
    responsible_user_id: uuid.UUID | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    result: TaskResult | None = None,
    unresolved: bool | None = None,
) -> tuple[list[Task], int]:
    filters = [Task.workspace_id == workspace_id]
    if planned_from is not None:
        filters.append(Task.planned_date >= planned_from)
    if planned_until is not None:
        filters.append(Task.planned_date <= planned_until)
    if responsible_user_id is not None:
        filters.append(Task.responsible_user_id == responsible_user_id)
    if master_task_id is not None:
        filters.append(Task.master_task_id == master_task_id)
    if category_id is not None:
        filters.append(MasterTask.category_id == category_id)
    if result is not None:
        filters.append(Task.result == result)
    if unresolved is True:
        filters.append(Task.result.is_(None))
    elif unresolved is False:
        filters.append(Task.result.is_not(None))
    joined = category_id is not None
    count_statement = select(func.count()).select_from(Task)
    items_statement = select(Task).options(selectinload(Task.master_task).selectinload(MasterTask.category))
    if joined:
        count_statement = count_statement.join(MasterTask, Task.master_task_id == MasterTask.id)
        items_statement = items_statement.join(MasterTask, Task.master_task_id == MasterTask.id)
    total = db.scalar(count_statement.where(*filters)) or 0
    items = list(db.scalars(items_statement.where(*filters).order_by(Task.planned_date.desc(), Task.id).offset((page - 1) * page_size).limit(page_size)).all())
    return items, total


def get_task(db: Session, *, workspace_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.scalar(
        select(Task)
        .options(selectinload(Task.master_task).selectinload(MasterTask.category))
        .where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if task is None:
        raise TaskNotFoundError("Task not found")
    return task


def update_task(
    db: Session,
    *,
    access: WorkspaceAccess,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    local_date: date,
) -> Task:
    task = _task(db, workspace_id=access.workspace.id, task_id=task_id, lock=True)
    if (
        task.result is not None
        or task.generation_batch_id is not None
        or task.planned_date <= local_date
    ):
        raise TaskConflictError("Task cannot be edited")
    if task.lock_version != task_in.lock_version:
        raise TaskConflictError("Task version conflict")
    values = task_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    if "master_task_id" in values:
        _master(db, workspace_id=access.workspace.id, master_task_id=values["master_task_id"], assignable=True)
    if "responsible_user_id" in values:
        _responsible(db, workspace_id=access.workspace.id, user_id=values["responsible_user_id"])
    for field, value in values.items():
        setattr(task, field, value)
    task.lock_version += 1
    _flush(db)
    return task


def resolve_task(
    db: Session,
    *,
    access: WorkspaceAccess,
    actor: User,
    task_id: uuid.UUID,
    expected_version: int,
    result: TaskResult,
    local_date: date,
    now: datetime | None = None,
) -> Task:
    task = _task(db, workspace_id=access.workspace.id, task_id=task_id, lock=True)
    if task.responsible_user_id != actor.id:
        raise TaskPermissionError("Only the responsible user may resolve the Task")
    if task.result is not None or task.planned_date > local_date or task.lock_version != expected_version:
        raise TaskConflictError("Task cannot be resolved")
    task.result = result
    task.resolved_at = now or datetime.now(timezone.utc)
    task.resolved_by_user_id = actor.id
    task.lock_version += 1
    _flush(db)
    return task


def delete_task(db: Session, *, access: WorkspaceAccess, task_id: uuid.UUID, expected_version: int, local_date: date) -> None:
    task = _task(db, workspace_id=access.workspace.id, task_id=task_id, lock=True)
    if task.lock_version != expected_version:
        raise TaskConflictError("Task version conflict")
    if task.result is not None or task.generation_batch_id is not None or task.planned_date <= local_date:
        raise TaskConflictError("Task cannot be deleted")
    db.delete(task)
    _flush(db)


def task_projection(db: Session, *, task: Task, actor_id: uuid.UUID, local_date: date) -> tuple[User, str, bool, bool, bool]:
    master = task.master_task if "master_task" in task.__dict__ else db.scalar(select(MasterTask).options(selectinload(MasterTask.category)).where(MasterTask.id == task.master_task_id))
    if master is None:
        raise TaskNotFoundError("Task not found")
    task.master_task = master
    responsible = db.scalar(select(User).where(User.id == task.responsible_user_id))
    if responsible is None:
        raise TaskNotFoundError("Task not found")
    state = "COMPLETADA" if task.result == TaskResult.COMPLETED else "NO_REALIZADA" if task.result == TaskResult.NOT_COMPLETED else "PROGRAMADA" if task.planned_date > local_date else "PENDIENTE"
    unresolved_standalone = task.result is None and task.generation_batch_id is None
    future_standalone = unresolved_standalone and task.planned_date > local_date
    can_resolve = task.result is None and task.planned_date <= local_date and task.responsible_user_id == actor_id
    return responsible, state, future_standalone, can_resolve, future_standalone
