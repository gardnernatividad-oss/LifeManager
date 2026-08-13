import uuid

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.task import (
    TaskBulkCreate,
    TaskBulkCreateResponse,
    TaskBulkDelete,
    TaskBulkDeleteResponse,
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from app.services import task_service


router = APIRouter(prefix="/tasks", tags=["Task Planning"])

_DOMAIN_ERRORS = (
    task_service.TaskNotFoundError,
    task_service.TaskMasterTaskNotFoundError,
    task_service.TaskOccurrenceConflictError,
    task_service.TaskPlanningConflictError,
    task_service.TaskVersionConflictError,
    task_service.TaskBulkValidationError,
)


def _task_error(error: Exception) -> HTTPException:
    if isinstance(error, task_service.TaskNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, task_service.TaskMasterTaskNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, task_service.TaskBulkValidationError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(
        error,
        (
            task_service.TaskOccurrenceConflictError,
            task_service.TaskPlanningConflictError,
            task_service.TaskVersionConflictError,
        ),
    ):
        return HTTPException(status_code=409, detail=str(error))
    raise error


def _today(current_user: CurrentUser) -> date:
    return local_today(current_user.timezone)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: TaskCreate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> TaskRead:
    try:
        task = task_service.create_task(
            db,
            workspace_id=workspace.id,
            current_user=current_user,
            task_in=task_in,
        )
        db.commit()
        db.refresh(task)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return TaskRead.from_task(task, local_date=_today(current_user))


@router.post("/bulk", response_model=TaskBulkCreateResponse, status_code=201)
def create_tasks_bulk(
    task_in: TaskBulkCreate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> TaskBulkCreateResponse:
    try:
        tasks = task_service.create_tasks_bulk(
            db,
            workspace_id=workspace.id,
            current_user=current_user,
            task_in=task_in,
        )
        db.commit()
        for task in tasks:
            db.refresh(task)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _task_error(error) from error
    except Exception:
        db.rollback()
        raise
    today = _today(current_user)
    return TaskBulkCreateResponse(
        created_count=len(tasks),
        items=[TaskRead.from_task(task, local_date=today) for task in tasks],
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    planned_from: date | None = None,
    planned_to: date | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
) -> TaskListResponse:
    if planned_from is not None and planned_to is not None and planned_from > planned_to:
        raise HTTPException(status_code=422, detail="planned_from must not exceed planned_to")
    today = _today(current_user)
    try:
        items, total = task_service.list_tasks(
            db,
            workspace_id=workspace.id,
            local_date=today,
            page=page,
            page_size=page_size,
            planned_from=planned_from,
            planned_to=planned_to,
            master_task_id=master_task_id,
            category_id=category_id,
            status=task_status,
        )
    except _DOMAIN_ERRORS as error:
        raise _task_error(error) from error
    return TaskListResponse(
        items=[TaskRead.from_task(task, local_date=today) for task in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> TaskRead:
    today = _today(current_user)
    try:
        task = task_service.update_task(
            db,
            workspace_id=workspace.id,
            task_id=task_id,
            task_in=task_in,
            local_date=today,
        )
        db.commit()
        db.refresh(task)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return TaskRead.from_task(task, local_date=today)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
    lock_version: int = Query(ge=1),
) -> Response:
    try:
        task_service.delete_task(
            db,
            workspace_id=workspace.id,
            task_id=task_id,
            lock_version=lock_version,
            local_date=_today(current_user),
        )
        db.commit()
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk-delete", response_model=TaskBulkDeleteResponse)
def delete_tasks_bulk(
    task_in: TaskBulkDelete,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> TaskBulkDeleteResponse:
    try:
        deleted_count = task_service.delete_tasks_bulk(
            db,
            workspace_id=workspace.id,
            task_in=task_in,
            local_date=_today(current_user),
        )
        db.commit()
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return TaskBulkDeleteResponse(deleted_count=deleted_count)
