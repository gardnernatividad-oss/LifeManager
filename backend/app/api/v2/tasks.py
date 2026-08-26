import math
import uuid

from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.models import Task, User
from app.models.enums import TaskResult
from app.schemas.v2_task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate, TaskVersionRequest
from app.services.v2_task import (
    TaskConflictError,
    TaskNotFoundError,
    TaskPermissionError,
    TaskReferenceUnavailableError,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    resolve_task,
    task_projection,
    update_task,
)


router = APIRouter(prefix="/workspaces/{workspace_id}/tasks", tags=["V2 Tasks"])


def _raise_domain_error(error: ValueError) -> None:
    if isinstance(error, TaskNotFoundError):
        raise V2APIError(status_code=404, code="TASK_NOT_FOUND", message="No se encontró la tarea.") from error
    if isinstance(error, TaskReferenceUnavailableError):
        raise V2APIError(status_code=404, code="TASK_REFERENCE_UNAVAILABLE", message="La referencia de la tarea no está disponible.") from error
    if isinstance(error, TaskPermissionError):
        raise V2APIError(status_code=403, code="TASK_PERMISSION_DENIED", message="No tienes permiso para resolver esta tarea.") from error
    raise V2APIError(status_code=409, code="TASK_CONFLICT", message="La tarea cambió o no admite esta acción.") from error


def _read(db: SessionDependency, task: Task, account: User, today: date) -> TaskRead:
    responsible, state, can_edit, can_resolve, can_delete = task_projection(
        db, task=task, actor_id=account.id, local_date=today
    )
    master = task.master_task
    return TaskRead(
        id=task.id,
        workspace_id=task.workspace_id,
        master_task_id=task.master_task_id,
        master_task_name=master.name,
        category_id=master.category_id,
        category_name=master.category.name,
        responsible_user_id=task.responsible_user_id,
        responsible_display_name=f"{responsible.first_name} {responsible.last_name}".strip(),
        responsible_email=responsible.email,
        planned_date=task.planned_date,
        state=state,
        result=task.result,
        resolved_at=task.resolved_at,
        resolved_by_user_id=task.resolved_by_user_id,
        lock_version=task.lock_version,
        can_edit=can_edit,
        can_resolve=can_resolve,
        can_delete=can_delete,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _write(db: SessionDependency, operation):
    try:
        task = operation()
        db.commit()
        if task is not None:
            db.refresh(task)
        return task
    except (TaskNotFoundError, TaskConflictError, TaskPermissionError, TaskReferenceUnavailableError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create(
    workspace_id: uuid.UUID,
    task_in: TaskCreate,
    db: SessionDependency,
    account: UsableAccount,
    access: ActiveWorkspaceMembership,
) -> TaskRead:
    del workspace_id
    task = _write(db, lambda: create_task(db, access=access, actor=account, task_in=task_in))
    return _read(db, task, account, local_today(account.timezone))


@router.get("", response_model=TaskListResponse)
def index(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    account: UsableAccount,
    access: ActiveWorkspaceMembership,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    planned_from: date | None = None,
    planned_until: date | None = None,
    responsible_user_id: uuid.UUID | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    result: TaskResult | None = None,
    unresolved: bool | None = None,
) -> TaskListResponse:
    del access
    if planned_from is not None and planned_until is not None and planned_from > planned_until:
        raise V2APIError(status_code=422, code="INVALID_DATE_RANGE", message="El rango de fechas no es válido.")
    items, total = list_tasks(
        db,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        planned_from=planned_from,
        planned_until=planned_until,
        responsible_user_id=responsible_user_id,
        master_task_id=master_task_id,
        category_id=category_id,
        result=result,
        unresolved=unresolved,
    )
    today = local_today(account.timezone)
    return TaskListResponse(
        items=[_read(db, item, account, today) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


@router.get("/{task_id}", response_model=TaskRead)
def detail(workspace_id: uuid.UUID, task_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> TaskRead:
    del access
    try:
        return _read(db, get_task(db, workspace_id=workspace_id, task_id=task_id), account, local_today(account.timezone))
    except TaskNotFoundError as error:
        _raise_domain_error(error)


@router.patch("/{task_id}", response_model=TaskRead)
def patch(workspace_id: uuid.UUID, task_id: uuid.UUID, task_in: TaskUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> TaskRead:
    del workspace_id
    task = _write(
        db,
        lambda: update_task(
            db,
            access=access,
            task_id=task_id,
            task_in=task_in,
            local_date=local_today(account.timezone),
        ),
    )
    return _read(db, task, account, local_today(account.timezone))


def _resolve(task_id: uuid.UUID, resolution_in: TaskVersionRequest, db: SessionDependency, account: User, access, result: TaskResult) -> TaskRead:
    today = local_today(account.timezone)
    task = _write(db, lambda: resolve_task(db, access=access, actor=account, task_id=task_id, expected_version=resolution_in.lock_version, result=result, local_date=today))
    return _read(db, task, account, today)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete(workspace_id: uuid.UUID, task_id: uuid.UUID, resolution_in: TaskVersionRequest, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> TaskRead:
    del workspace_id
    return _resolve(task_id, resolution_in, db, account, access, TaskResult.COMPLETED)


@router.post("/{task_id}/not-complete", response_model=TaskRead)
def not_complete(workspace_id: uuid.UUID, task_id: uuid.UUID, resolution_in: TaskVersionRequest, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> TaskRead:
    del workspace_id
    return _resolve(task_id, resolution_in, db, account, access, TaskResult.NOT_COMPLETED)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(workspace_id: uuid.UUID, task_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, lock_version: int = Query(ge=1)) -> Response:
    del workspace_id
    _write(db, lambda: delete_task(db, access=access, task_id=task_id, expected_version=lock_version, local_date=local_today(account.timezone)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
