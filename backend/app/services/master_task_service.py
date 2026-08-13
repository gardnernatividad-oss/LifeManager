import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.names import normalize_name
from app.models import Category, MasterTask, Task
from app.schemas.master_task import MasterTaskCreate, MasterTaskUpdate


class MasterTaskNotFoundError(LookupError):
    pass


class MasterTaskCategoryNotFoundError(LookupError):
    pass


class MasterTaskNameConflictError(ValueError):
    pass


class MasterTaskInUseError(ValueError):
    pass


_MASTER_TASK_UNIQUE_CONSTRAINT = "uq_master_tasks_workspace_id_normalized_name"
_MASTER_TASK_REFERENCE_CONSTRAINT = "fk_tasks_master_task_workspace"


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint_name = _constraint_name(error)
        if constraint_name == _MASTER_TASK_UNIQUE_CONSTRAINT:
            raise MasterTaskNameConflictError("Master task name already exists") from error
        if constraint_name == _MASTER_TASK_REFERENCE_CONSTRAINT:
            raise MasterTaskInUseError("Master task is already in use") from error
        raise


def _get_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    for_update: bool = False,
) -> Category:
    statement = select(Category).where(
        Category.id == category_id,
        Category.workspace_id == workspace_id,
    )
    if for_update:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None:
        raise MasterTaskCategoryNotFoundError("Category not found")
    return category


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
        raise MasterTaskNotFoundError("Master task not found")
    return master_task


def _name_exists(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    normalized_name: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    statement = select(MasterTask.id).where(
        MasterTask.workspace_id == workspace_id,
        MasterTask.normalized_name == normalized_name,
    )
    if exclude_id is not None:
        statement = statement.where(MasterTask.id != exclude_id)
    return db.scalar(statement) is not None


def _is_used(db: Session, *, master_task_id: uuid.UUID) -> bool:
    return bool(db.scalar(select(exists().where(Task.master_task_id == master_task_id))))


def create_master_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    master_task_in: MasterTaskCreate,
) -> MasterTask:
    category = _get_category(
        db,
        workspace_id=workspace_id,
        category_id=master_task_in.category_id,
        for_update=True,
    )
    name, normalized_name = normalize_name(
        master_task_in.name, max_length=150, field_label="Master task"
    )
    if _name_exists(db, workspace_id=workspace_id, normalized_name=normalized_name):
        raise MasterTaskNameConflictError("Master task name already exists")
    master_task = MasterTask(
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name=name,
        normalized_name=normalized_name,
    )
    db.add(master_task)
    _flush(db)
    return master_task


def list_master_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    category_id: uuid.UUID | None = None,
) -> tuple[list[MasterTask], int]:
    filters = [MasterTask.workspace_id == workspace_id]
    if category_id is not None:
        _get_category(db, workspace_id=workspace_id, category_id=category_id)
        filters.append(MasterTask.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(MasterTask).where(*filters)) or 0
    statement = (
        select(MasterTask)
        .options(selectinload(MasterTask.category))
        .where(*filters)
        .order_by(MasterTask.normalized_name, MasterTask.name, MasterTask.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), total


def update_master_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    master_task_id: uuid.UUID,
    master_task_in: MasterTaskUpdate,
) -> MasterTask:
    master_task = _get_master_task(
        db,
        workspace_id=workspace_id,
        master_task_id=master_task_id,
        for_update=True,
    )
    changes = master_task_in.model_dump(exclude_unset=True)
    if not changes:
        return master_task
    if _is_used(db, master_task_id=master_task.id):
        raise MasterTaskInUseError("Master task is already in use")
    if "name" in changes:
        name, normalized_name = normalize_name(
            changes["name"], max_length=150, field_label="Master task"
        )
        if normalized_name != master_task.normalized_name and _name_exists(
            db,
            workspace_id=workspace_id,
            normalized_name=normalized_name,
            exclude_id=master_task.id,
        ):
            raise MasterTaskNameConflictError("Master task name already exists")
        master_task.name = name
        master_task.normalized_name = normalized_name
    if "category_id" in changes and changes["category_id"] != master_task.category_id:
        category = _get_category(
            db,
            workspace_id=workspace_id,
            category_id=changes["category_id"],
            for_update=True,
        )
        master_task.category_id = category.id
        master_task.category = category
    _flush(db)
    return master_task


def delete_master_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    master_task_id: uuid.UUID,
) -> None:
    master_task = _get_master_task(
        db,
        workspace_id=workspace_id,
        master_task_id=master_task_id,
        for_update=True,
    )
    if _is_used(db, master_task_id=master_task.id):
        raise MasterTaskInUseError("Master task is already in use")
    db.delete(master_task)
    _flush(db)
