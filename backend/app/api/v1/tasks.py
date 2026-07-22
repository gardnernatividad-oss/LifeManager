import uuid

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.task import Task, TaskOutcome, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate
from app.services import task_resolution_service, task_service


router = APIRouter(prefix="/workspaces/{workspace_id}/tasks", tags=["Tasks"])

_DOMAIN_ERRORS = (
    task_service.TaskNotFoundError,
    task_service.TaskPermissionError,
    task_service.TaskCategoryNotFoundError,
    task_service.TaskCategoryInactiveError,
    task_service.TaskProjectNotFoundError,
    task_service.TaskProjectInactiveError,
    task_resolution_service.TaskNotFound,
    task_resolution_service.TaskPermission,
    task_resolution_service.TaskAlreadyResolved,
)


def _raise_http_error(error: Exception) -> None:
    if isinstance(
        error,
        (
            task_service.TaskNotFoundError,
            task_service.TaskCategoryNotFoundError,
            task_service.TaskProjectNotFoundError,
            task_resolution_service.TaskNotFound,
        ),
    ):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(
        error,
        (
            task_service.TaskCategoryInactiveError,
            task_service.TaskProjectInactiveError,
            task_resolution_service.TaskAlreadyResolved,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, task_resolution_service.TaskPermission):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise HTTPException(status_code=403, detail=str(error)) from error


def _commit_task_write(
    db: Session,
    operation: Callable[..., Task],
    **kwargs: object,
) -> TaskRead:
    try:
        task = operation(db, **kwargs)
        db.commit()
        db.refresh(task)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return TaskRead.from_task(task)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    workspace_id: uuid.UUID,
    task_in: TaskCreate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    return _commit_task_write(
        db,
        task_service.create_task,
        workspace_id=workspace_id,
        current_user=current_user,
        task_in=task_in,
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    category_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    order_by: Literal["scheduled_at", "created_at", "updated_at", "title"] = "scheduled_at",
    order_direction: Literal["asc", "desc"] = "asc",
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    outcome: TaskOutcome | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    search: str | None = None,
) -> TaskListResponse:
    try:
        items, total = task_service.list_tasks(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            category_id=category_id,
            project_id=project_id,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_direction=order_direction,
            status=status_filter,
            outcome=outcome,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            search=search,
        )
    except _DOMAIN_ERRORS as error:
        _raise_http_error(error)
    boundary = datetime.now(timezone.utc)
    return TaskListResponse(
        items=[TaskRead.from_task(item, now=boundary) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    try:
        task = task_service.get_task(
            db,
            workspace_id=workspace_id,
            task_id=task_id,
            current_user=current_user,
        )
    except _DOMAIN_ERRORS as error:
        _raise_http_error(error)
    return TaskRead.from_task(task)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    return _commit_task_write(
        db,
        task_service.update_task,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
        task_in=task_in,
    )


def _transition(
    db: Session,
    operation: Callable[..., Task],
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> TaskRead:
    return _commit_task_write(
        db,
        operation,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
    )


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    return _transition(
        db,
        task_resolution_service.complete_task,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
    )


@router.post("/{task_id}/not-complete", response_model=TaskRead)
def mark_task_not_completed(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    return _transition(
        db,
        task_resolution_service.mark_task_not_completed,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
    )


@router.post("/{task_id}/cancel", response_model=TaskRead)
def cancel_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    return _transition(
        db,
        task_resolution_service.cancel_task,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
    )
