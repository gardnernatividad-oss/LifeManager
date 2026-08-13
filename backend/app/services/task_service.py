import uuid

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings
from app.models import Category, MasterTask, Task, TaskResult, User
from app.schemas.task import (
    BulkTaskPattern,
    TaskBulkCreate,
    TaskBulkDelete,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    TaskResultUpdate,
)


class TaskNotFoundError(LookupError):
    pass


class TaskMasterTaskNotFoundError(LookupError):
    pass


class TaskOccurrenceConflictError(ValueError):
    pass


class TaskPlanningConflictError(ValueError):
    pass


class TaskVersionConflictError(ValueError):
    pass


class TaskBulkValidationError(ValueError):
    pass


class TaskResultConflictError(ValueError):
    pass


_TASK_UNIQUE_CONSTRAINT = "uq_tasks_workspace_id_master_task_id_planned_date"


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        if _constraint_name(error) == _TASK_UNIQUE_CONSTRAINT:
            raise TaskOccurrenceConflictError("Task occurrence already exists") from error
        raise


def _task_options():
    return selectinload(Task.master_task).selectinload(MasterTask.category)


def _get_master_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    master_task_id: uuid.UUID,
    for_update: bool = False,
) -> MasterTask:
    statement = (
        select(MasterTask)
        .options(selectinload(MasterTask.category))
        .where(
            MasterTask.id == master_task_id,
            MasterTask.workspace_id == workspace_id,
        )
    )
    if for_update:
        statement = statement.with_for_update()
    master_task = db.scalar(statement)
    if master_task is None:
        raise TaskMasterTaskNotFoundError("Master task not found")
    return master_task


def _get_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    for_update: bool = False,
) -> Task:
    statement = (
        select(Task)
        .options(_task_options())
        .where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if for_update:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise TaskNotFoundError("Task not found")
    return task


def _is_programada(task: Task, *, local_date: date) -> bool:
    return task.result is None and task.planned_date > local_date


def _dates_for_bulk(request: TaskBulkCreate) -> list[date]:
    dates: list[date]
    if request.pattern is BulkTaskPattern.DAILY:
        count = (request.end_date - request.start_date).days + 1
        if count > settings.TASK_BULK_MAX_OCCURRENCES:
            raise TaskBulkValidationError(
                "Bulk request exceeds the configured safeguard of "
                f"{settings.TASK_BULK_MAX_OCCURRENCES} occurrences"
            )
        dates = [request.start_date + timedelta(days=offset) for offset in range(count)]
    elif request.pattern is BulkTaskPattern.WEEKLY:
        dates = []
        for weekday in request.weekdays or []:
            candidate = request.start_date + timedelta(
                days=(weekday - request.start_date.weekday()) % 7
            )
            while candidate <= request.end_date:
                dates.append(candidate)
                if len(dates) > settings.TASK_BULK_MAX_OCCURRENCES:
                    raise TaskBulkValidationError(
                        "Bulk request exceeds the configured safeguard of "
                        f"{settings.TASK_BULK_MAX_OCCURRENCES} occurrences"
                    )
                candidate += timedelta(days=7)
        dates.sort()
    if not dates:
        raise TaskBulkValidationError("Bulk request does not produce any dates")
    if len(set(dates)) != len(dates):
        raise TaskBulkValidationError("Bulk request produced duplicate dates")
    return dates


def create_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    task_in: TaskCreate,
) -> Task:
    master_task = _get_master_task(
        db,
        workspace_id=workspace_id,
        master_task_id=task_in.master_task_id,
        for_update=True,
    )
    conflict = db.scalar(
        select(Task.id).where(
            Task.workspace_id == workspace_id,
            Task.master_task_id == master_task.id,
            Task.planned_date == task_in.planned_date,
        )
    )
    if conflict is not None:
        raise TaskOccurrenceConflictError("Task occurrence already exists")
    task = Task(
        workspace_id=workspace_id,
        master_task_id=master_task.id,
        master_task=master_task,
        planned_date=task_in.planned_date,
        result=None,
        resolved_at=None,
        resolved_by_id=None,
        created_by_id=current_user.id,
        lock_version=1,
    )
    db.add(task)
    _flush(db)
    return task


def create_tasks_bulk(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    task_in: TaskBulkCreate,
) -> list[Task]:
    master_task = _get_master_task(
        db,
        workspace_id=workspace_id,
        master_task_id=task_in.master_task_id,
        for_update=True,
    )
    planned_dates = _dates_for_bulk(task_in)
    conflicts = list(
        db.scalars(
            select(Task.planned_date).where(
                Task.workspace_id == workspace_id,
                Task.master_task_id == master_task.id,
                Task.planned_date.in_(planned_dates),
            )
        ).all()
    )
    if conflicts:
        raise TaskOccurrenceConflictError("One or more Task occurrences already exist")
    tasks = [
        Task(
            workspace_id=workspace_id,
            master_task_id=master_task.id,
            master_task=master_task,
            planned_date=planned_date,
            result=None,
            resolved_at=None,
            resolved_by_id=None,
            created_by_id=current_user.id,
            lock_version=1,
        )
        for planned_date in planned_dates
    ]
    db.add_all(tasks)
    _flush(db)
    return tasks


def list_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    local_date: date,
    page: int,
    page_size: int,
    planned_from: date | None = None,
    planned_to: date | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
) -> tuple[list[Task], int]:
    filters = [Task.workspace_id == workspace_id]
    if planned_from is not None:
        filters.append(Task.planned_date >= planned_from)
    if planned_to is not None:
        filters.append(Task.planned_date <= planned_to)
    if master_task_id is not None:
        _get_master_task(db, workspace_id=workspace_id, master_task_id=master_task_id)
        filters.append(Task.master_task_id == master_task_id)
    if category_id is not None:
        category_exists = db.scalar(
            select(Category.id).where(
                Category.id == category_id,
                Category.workspace_id == workspace_id,
            )
        )
        if category_exists is None:
            raise TaskMasterTaskNotFoundError("Category not found")
        filters.append(MasterTask.category_id == category_id)
    if status is TaskStatus.PROGRAMADA:
        filters.extend((Task.result.is_(None), Task.planned_date > local_date))
    elif status is TaskStatus.PENDIENTE:
        filters.extend((Task.result.is_(None), Task.planned_date <= local_date))
    elif status is TaskStatus.COMPLETADA:
        filters.append(Task.result == TaskResult.COMPLETED)
    elif status is TaskStatus.NO_REALIZADA:
        filters.append(Task.result == TaskResult.NOT_COMPLETED)

    count_statement = select(func.count()).select_from(Task)
    statement = select(Task).options(_task_options())
    if category_id is not None:
        count_statement = count_statement.join(MasterTask)
        statement = statement.join(MasterTask)
    total = db.scalar(count_statement.where(*filters)) or 0
    statement = (
        statement.where(*filters)
        .order_by(Task.planned_date, Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), int(total)


def update_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    local_date: date,
) -> Task:
    task = _get_task(db, workspace_id=workspace_id, task_id=task_id)
    if not _is_programada(task, local_date=local_date):
        raise TaskPlanningConflictError("Only scheduled Tasks can be edited")
    statement = (
        update(Task)
        .where(
            Task.id == task_id,
            Task.workspace_id == workspace_id,
            Task.lock_version == task_in.lock_version,
        )
        .values(planned_date=task_in.planned_date, lock_version=Task.lock_version + 1)
        .execution_options(synchronize_session=False)
    )
    try:
        result = db.execute(statement)
    except IntegrityError as error:
        if _constraint_name(error) == _TASK_UNIQUE_CONSTRAINT:
            raise TaskOccurrenceConflictError("Task occurrence already exists") from error
        raise
    if result.rowcount != 1:
        raise TaskVersionConflictError("Task version is stale")
    set_committed_value(task, "planned_date", task_in.planned_date)
    set_committed_value(task, "lock_version", task_in.lock_version + 1)
    db.flush()
    return task


def set_task_result(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
    result_in: TaskResultUpdate,
    local_date: date,
    resolved_at: datetime | None = None,
) -> Task:
    task = _get_task(db, workspace_id=workspace_id, task_id=task_id)
    if task.lock_version != result_in.lock_version:
        raise TaskVersionConflictError("Task version is stale")
    if task.result is None:
        if task.planned_date > local_date:
            raise TaskResultConflictError("Scheduled Tasks cannot receive a result")
        expected_result = None
    else:
        if task.result == result_in.result or task.result == result_in.result.value:
            raise TaskResultConflictError("Task already has the requested result")
        expected_result = task.result

    resolution_time = resolved_at or datetime.now(timezone.utc)
    if resolution_time.tzinfo is None or resolution_time.utcoffset() is None:
        raise ValueError("resolved_at must be timezone-aware")
    resolution_time = resolution_time.astimezone(timezone.utc)

    result = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.workspace_id == workspace_id,
            Task.lock_version == result_in.lock_version,
            Task.result == expected_result if expected_result is not None else Task.result.is_(None),
        )
        .values(
            result=result_in.result,
            resolved_at=resolution_time,
            resolved_by_id=current_user.id,
            lock_version=Task.lock_version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise TaskVersionConflictError("Task version is stale")

    set_committed_value(task, "result", result_in.result)
    set_committed_value(task, "resolved_at", resolution_time)
    set_committed_value(task, "resolved_by_id", current_user.id)
    set_committed_value(task, "lock_version", result_in.lock_version + 1)
    db.flush()
    return task


def delete_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    lock_version: int,
    local_date: date,
) -> None:
    task = _get_task(db, workspace_id=workspace_id, task_id=task_id, for_update=True)
    if task.lock_version != lock_version:
        raise TaskVersionConflictError("Task version is stale")
    if not _is_programada(task, local_date=local_date):
        raise TaskPlanningConflictError("Only scheduled Tasks can be deleted")
    db.delete(task)
    _flush(db)


def delete_tasks_bulk(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_in: TaskBulkDelete,
    local_date: date,
) -> int:
    expected_versions = {item.id: item.lock_version for item in task_in.items}
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.workspace_id == workspace_id, Task.id.in_(expected_versions))
            .with_for_update()
        ).all()
    )
    if len(tasks) != len(expected_versions):
        raise TaskNotFoundError("One or more Tasks were not found")
    if any(task.lock_version != expected_versions[task.id] for task in tasks):
        raise TaskVersionConflictError("One or more Task versions are stale")
    if any(not _is_programada(task, local_date=local_date) for task in tasks):
        raise TaskPlanningConflictError("All selected Tasks must be scheduled")
    for task in tasks:
        db.delete(task)
    _flush(db)
    return len(tasks)
