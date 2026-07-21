import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate
from app.services import task_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/tasks",
    tags=["Tasks"],
)


def _raise_http_error(error: Exception) -> None:
    if isinstance(
        error,
        (task_service.TaskNotFoundError, task_service.TaskCategoryNotFoundError),
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    if isinstance(error, task_service.TaskCategoryInactiveError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is inactive",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(error),
    ) from error


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    workspace_id: uuid.UUID,
    task_in: TaskCreate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    try:
        task = task_service.create_task(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            task_in=task_in,
        )
        db.commit()
        db.refresh(task)
    except (
        task_service.TaskNotFoundError,
        task_service.TaskPermissionError,
        task_service.TaskCategoryNotFoundError,
        task_service.TaskCategoryInactiveError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return TaskRead.model_validate(task)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    category_id: uuid.UUID | None = None,
) -> TaskListResponse:
    try:
        items, total = task_service.list_tasks(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            category_id=category_id,
        )
    except (
        task_service.TaskNotFoundError,
        task_service.TaskPermissionError,
        task_service.TaskCategoryNotFoundError,
        task_service.TaskCategoryInactiveError,
    ) as error:
        _raise_http_error(error)
    return TaskListResponse(items=items, total=total)


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
    except (
        task_service.TaskNotFoundError,
        task_service.TaskPermissionError,
        task_service.TaskCategoryNotFoundError,
        task_service.TaskCategoryInactiveError,
    ) as error:
        _raise_http_error(error)
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> TaskRead:
    try:
        task = task_service.update_task(
            db,
            workspace_id=workspace_id,
            task_id=task_id,
            current_user=current_user,
            task_in=task_in,
        )
        db.commit()
        db.refresh(task)
    except (
        task_service.TaskNotFoundError,
        task_service.TaskPermissionError,
        task_service.TaskCategoryNotFoundError,
        task_service.TaskCategoryInactiveError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return TaskRead.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_task(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> Response:
    try:
        task_service.delete_task(
            db,
            workspace_id=workspace_id,
            task_id=task_id,
            current_user=current_user,
        )
        db.commit()
    except (
        task_service.TaskNotFoundError,
        task_service.TaskPermissionError,
        task_service.TaskCategoryNotFoundError,
        task_service.TaskCategoryInactiveError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
