import uuid

from datetime import date, datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.recurrence import recurrence_dates
from app.core.names import normalize_name
from app.models import Category, GenerationBatch, MasterTask, Task, User, WorkspaceMember
from app.models.enums import AccountStatus, GenerationEntityType, MembershipStatus, TaskResult, WorkspaceKind
from app.schemas.v2_task import RecurringTaskCreate, TaskCreate, TaskMutationScope, TaskState, TaskUpdate
from app.services.v2_workspace import WorkspaceAccess


class TaskNotFoundError(LookupError):
    pass


class TaskConflictError(ValueError):
    pass


class TaskPermissionError(ValueError):
    pass


class TaskReferenceUnavailableError(ValueError):
    pass


class TaskRecurrenceError(ValueError):
    pass


MAX_RECURRING_TASK_OCCURRENCES = 1000


def _translate_integrity(error: IntegrityError) -> None:
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
    if constraint in {"uq_tasks_workspace_master_date_responsible", "uq_tasks_catalog_occurrence", "uq_tasks_custom_occurrence"}:
        raise TaskConflictError("Task occurrence already exists") from error
    if constraint in {
        "fk_tasks_master_task_workspace",
        "fk_tasks_custom_category_workspace",
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


def _category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, assignable: bool) -> Category:
    statement = select(Category).where(Category.id == category_id, Category.workspace_id == workspace_id)
    if assignable:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None or (assignable and not category.is_active):
        raise TaskReferenceUnavailableError("Task Category unavailable")
    return category


def _source_values(db: Session, *, workspace_id: uuid.UUID, source) -> dict[str, object | None]:
    if source.master_task_id is not None:
        _master(db, workspace_id=workspace_id, master_task_id=source.master_task_id, assignable=True)
        return {"master_task_id": source.master_task_id, "custom_name": None, "custom_category_id": None}
    name, _ = normalize_name(source.custom_name, max_length=150, field_label="Task")
    _category(db, workspace_id=workspace_id, category_id=source.custom_category_id, assignable=True)
    return {"master_task_id": None, "custom_name": name, "custom_category_id": source.custom_category_id}


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
    source = _source_values(db, workspace_id=access.workspace.id, source=task_in)
    responsible_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (task_in.responsible_user_id or actor.id)
    _responsible(db, workspace_id=access.workspace.id, user_id=responsible_id)
    task = Task(
        workspace_id=access.workspace.id,
        **source,
        responsible_user_id=responsible_id,
        planned_date=task_in.planned_date,
        created_by_user_id=actor.id,
        generation_batch_id=None,
    )
    db.add(task)
    _flush(db)
    return task


def create_recurring_tasks(
    db: Session,
    *,
    access: WorkspaceAccess,
    actor: User,
    task_in: RecurringTaskCreate,
) -> list[Task]:
    source = _source_values(db, workspace_id=access.workspace.id, source=task_in)
    responsible_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (task_in.responsible_user_id or actor.id)
    _responsible(db, workspace_id=access.workspace.id, user_id=responsible_id)
    recurrence = task_in.recurrence
    dates = recurrence_dates(
        pattern=recurrence.pattern,
        date_from=recurrence.date_from,
        date_until=recurrence.date_until,
        weekdays=recurrence.weekdays,
        month_days=recurrence.month_days,
    )
    if not dates:
        raise TaskRecurrenceError("Recurrence must generate at least one occurrence")
    if len(dates) > MAX_RECURRING_TASK_OCCURRENCES:
        raise TaskRecurrenceError("Recurrence exceeds occurrence limit")
    batch = GenerationBatch(
        workspace_id=access.workspace.id,
        entity_type=GenerationEntityType.TASK,
        pattern=recurrence.pattern,
        date_from=recurrence.date_from,
        date_until=recurrence.date_until,
        weekdays=recurrence.weekdays,
        month_days=recurrence.month_days,
        timezone=None,
        created_by_user_id=actor.id,
    )
    db.add(batch)
    _flush(db)
    tasks = [
        Task(
            workspace_id=access.workspace.id,
            **source,
            responsible_user_id=responsible_id,
            planned_date=planned_date,
            created_by_user_id=actor.id,
            generation_batch_id=batch.id,
        )
        for planned_date in dates
    ]
    db.add_all(tasks)
    _flush(db)
    return tasks


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
    state: TaskState | None = None,
    generated: bool | None = None,
    custom: bool | None = None,
    local_date: date | None = None,
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
        filters.append(or_(MasterTask.category_id == category_id, Task.custom_category_id == category_id))
    if result is not None:
        filters.append(Task.result == result)
    if unresolved is True:
        filters.append(Task.result.is_(None))
    elif unresolved is False:
        filters.append(Task.result.is_not(None))
    if state is not None:
        if local_date is None:
            raise ValueError("local_date is required for state filtering")
        if state == "PROGRAMADA":
            filters.extend((Task.result.is_(None), Task.planned_date > local_date))
        elif state == "PENDIENTE":
            filters.extend((Task.result.is_(None), Task.planned_date <= local_date))
        elif state == "COMPLETADA":
            filters.append(Task.result == TaskResult.COMPLETED)
        else:
            filters.append(Task.result == TaskResult.NOT_COMPLETED)
    if generated is True:
        filters.append(Task.generation_batch_id.is_not(None))
    elif generated is False:
        filters.append(Task.generation_batch_id.is_(None))
    if custom is True:
        filters.append(Task.master_task_id.is_(None))
    elif custom is False:
        filters.append(Task.master_task_id.is_not(None))
    joined = category_id is not None
    count_statement = select(func.count()).select_from(Task)
    items_statement = select(Task).options(selectinload(Task.master_task).selectinload(MasterTask.category))
    if joined:
        count_statement = count_statement.outerjoin(MasterTask, and_(Task.master_task_id == MasterTask.id, Task.workspace_id == MasterTask.workspace_id))
        items_statement = items_statement.outerjoin(MasterTask, and_(Task.master_task_id == MasterTask.id, Task.workspace_id == MasterTask.workspace_id))
    total = db.scalar(count_statement.where(*filters)) or 0
    items = list(db.scalars(items_statement.where(*filters).order_by(Task.planned_date, Task.id).offset((page - 1) * page_size).limit(page_size)).all())
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
    task, affected = _mutation_scope_tasks(
        db,
        workspace_id=access.workspace.id,
        task_id=task_id,
        scope=task_in.scope,
        local_date=local_date,
    )
    if task.result is not None or task.planned_date <= local_date:
        raise TaskConflictError("Task cannot be edited")
    if task.lock_version != task_in.lock_version:
        raise TaskConflictError("Task version conflict")
    values = task_in.model_dump(exclude_unset=True, exclude={"lock_version", "scope"})
    if task_in.scope == "THIS_AND_FUTURE" and "planned_date" in values:
        raise TaskConflictError("Future recurrence schedule editing is not supported")
    if "planned_date" in values and values["planned_date"] <= local_date:
        raise TaskConflictError("Task must remain in the future")
    source_fields = {"master_task_id", "custom_name", "custom_category_id"} & values.keys()
    if task.master_task_id is not None:
        if source_fields - {"master_task_id"}:
            raise TaskConflictError("Task source cannot be converted")
        if "master_task_id" in values:
            _master(db, workspace_id=access.workspace.id, master_task_id=values["master_task_id"], assignable=True)
    else:
        if "master_task_id" in source_fields:
            raise TaskConflictError("Task source cannot be converted")
        if "custom_name" in values:
            values["custom_name"], _ = normalize_name(values["custom_name"], max_length=150, field_label="Task")
        if "custom_category_id" in values:
            _category(db, workspace_id=access.workspace.id, category_id=values["custom_category_id"], assignable=True)
    if "responsible_user_id" in values:
        _responsible(db, workspace_id=access.workspace.id, user_id=values["responsible_user_id"])
    for affected_task in affected:
        for field, value in values.items():
            setattr(affected_task, field, value)
        affected_task.lock_version += 1
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


def correct_task_result(
    db: Session,
    *,
    access: WorkspaceAccess,
    actor: User,
    task_id: uuid.UUID,
    expected_version: int,
    result: TaskResult,
    now: datetime | None = None,
) -> Task:
    task = _task(db, workspace_id=access.workspace.id, task_id=task_id, lock=True)
    if task.responsible_user_id != actor.id:
        raise TaskPermissionError("Only the responsible user may correct the Task")
    if task.result is None or task.result == result or task.lock_version != expected_version:
        raise TaskConflictError("Task result cannot be corrected")
    task.result = result
    task.resolved_at = now or datetime.now(timezone.utc)
    task.resolved_by_user_id = actor.id
    task.lock_version += 1
    _flush(db)
    return task


def _mutation_scope_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    scope: TaskMutationScope,
    local_date: date,
) -> tuple[Task, list[Task]]:
    if scope == "THIS":
        task = _task(db, workspace_id=workspace_id, task_id=task_id, lock=True)
        return task, [task]
    identified = _task(db, workspace_id=workspace_id, task_id=task_id)
    if identified.generation_batch_id is None:
        raise TaskConflictError("Standalone Task does not support future scope")
    batch_tasks = list(
        db.scalars(
            select(Task)
            .where(Task.workspace_id == workspace_id, Task.generation_batch_id == identified.generation_batch_id)
            .order_by(Task.planned_date, Task.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    )
    task = next((candidate for candidate in batch_tasks if candidate.id == task_id), None)
    if task is None:
        raise TaskConflictError("Task changed during scope selection")
    affected = [
        candidate
        for candidate in batch_tasks
        if candidate.planned_date >= task.planned_date
        and candidate.planned_date > local_date
        and candidate.result is None
    ]
    if task not in affected:
        raise TaskConflictError("Task cannot initiate a future scope operation")
    return task, affected


def delete_task(
    db: Session,
    *,
    access: WorkspaceAccess,
    task_id: uuid.UUID,
    expected_version: int,
    local_date: date,
    scope: TaskMutationScope = "THIS",
) -> None:
    task, affected = _mutation_scope_tasks(
        db,
        workspace_id=access.workspace.id,
        task_id=task_id,
        scope=scope,
        local_date=local_date,
    )
    if task.lock_version != expected_version:
        raise TaskConflictError("Task version conflict")
    if task.result is not None or task.planned_date <= local_date:
        raise TaskConflictError("Task cannot be deleted")
    for affected_task in affected:
        db.delete(affected_task)
    _flush(db)


def task_source_projection(db: Session, *, task: Task):
    master = None
    if task.master_task_id is not None:
        master = task.master_task if "master_task" in task.__dict__ else db.scalar(select(MasterTask).options(selectinload(MasterTask.category)).where(MasterTask.id == task.master_task_id))
        if master is None:
            raise TaskNotFoundError("Task not found")
        category = master.category
        task_name = master.name
    else:
        category = db.scalar(select(Category).where(Category.id == task.custom_category_id, Category.workspace_id == task.workspace_id))
        task_name = task.custom_name
        if category is None or task_name is None:
            raise TaskNotFoundError("Task not found")
    return master, category, task_name


def task_projection(db: Session, *, task: Task, actor_id: uuid.UUID, local_date: date):
    responsible = db.scalar(select(User).where(User.id == task.responsible_user_id))
    if responsible is None:
        raise TaskNotFoundError("Task not found")
    state = "COMPLETADA" if task.result == TaskResult.COMPLETED else "NO_REALIZADA" if task.result == TaskResult.NOT_COMPLETED else "PROGRAMADA" if task.planned_date > local_date else "PENDIENTE"
    is_generated = task.generation_batch_id is not None
    future_unresolved = task.result is None and task.planned_date > local_date
    can_resolve = task.result is None and task.planned_date <= local_date and task.responsible_user_id == actor_id
    return responsible, state, is_generated, future_unresolved, future_unresolved and is_generated, can_resolve, future_unresolved, future_unresolved and is_generated
