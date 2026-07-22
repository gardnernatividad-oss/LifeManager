import uuid

from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.task_series import TaskSeries
from app.schemas.task_series import TaskSeriesCreate, TaskSeriesListResponse, TaskSeriesMaterializeRequest, TaskSeriesMaterializeResponse, TaskSeriesRead, TaskSeriesUpdate
from app.services import task_materialization_service, task_series_service


router = APIRouter(prefix="/workspaces/{workspace_id}/task-series", tags=["Task Series"])

_ERRORS = (
    task_series_service.TaskSeriesNotFoundError,
    task_series_service.TaskSeriesPermissionError,
    task_series_service.TaskSeriesCategoryNotFoundError,
    task_series_service.TaskSeriesCategoryInactiveError,
    task_series_service.TaskSeriesProjectNotFoundError,
    task_series_service.TaskSeriesProjectInactiveError,
    task_series_service.TaskSeriesRecurrenceValidationError,
)

_MATERIALIZATION_ERRORS = _ERRORS + (
    task_materialization_service.TaskMaterializationValidationError,
    task_materialization_service.TaskMaterializationConflictError,
)


def _raise(error: Exception) -> None:
    if isinstance(error, (task_series_service.TaskSeriesNotFoundError, task_series_service.TaskSeriesCategoryNotFoundError, task_series_service.TaskSeriesProjectNotFoundError)):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, task_series_service.TaskSeriesPermissionError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise HTTPException(status_code=409, detail=str(error)) from error


def _write(db: Session, operation: Callable[..., TaskSeries], **kwargs: object) -> TaskSeriesRead:
    try:
        series = operation(db, **kwargs); db.commit(); db.refresh(series)
    except _ERRORS as error:
        db.rollback(); _raise(error)
    except Exception:
        db.rollback(); raise
    return TaskSeriesRead.model_validate(series)


def _materialize(db: Session, operation: Callable[..., list], **kwargs: object) -> TaskSeriesMaterializeResponse:
    try:
        tasks = operation(db, **kwargs)
        db.commit()
        for task in tasks:
            db.refresh(task)
    except _MATERIALIZATION_ERRORS as error:
        db.rollback(); _raise(error)
    except Exception:
        db.rollback(); raise
    return TaskSeriesMaterializeResponse(
        generated_count=len(tasks),
        generated_task_ids=[task.id for task in tasks],
    )


@router.post("", response_model=TaskSeriesRead, status_code=201)
def create_task_series(workspace_id: uuid.UUID, series_in: TaskSeriesCreate, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesRead:
    return _write(db, task_series_service.create_task_series, workspace_id=workspace_id, current_user=current_user, series_in=series_in)


@router.get("", response_model=TaskSeriesListResponse)
def list_task_series(workspace_id: uuid.UUID, db: SessionDependency, current_user: CurrentUser, is_active: bool | None = None, category_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None) -> TaskSeriesListResponse:
    try:
        items, total = task_series_service.list_task_series(db, workspace_id=workspace_id, current_user=current_user, is_active=is_active, category_id=category_id, project_id=project_id)
    except _ERRORS as error: _raise(error)
    return TaskSeriesListResponse(items=items, total=total)


@router.post("/materialize", response_model=TaskSeriesMaterializeResponse)
def materialize_workspace_task_series(workspace_id: uuid.UUID, window: TaskSeriesMaterializeRequest, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesMaterializeResponse:
    return _materialize(db, task_materialization_service.materialize_workspace_task_series, workspace_id=workspace_id, current_user=current_user, window_start=window.window_start, window_end=window.window_end)


@router.get("/{series_id}", response_model=TaskSeriesRead)
def get_task_series(workspace_id: uuid.UUID, series_id: uuid.UUID, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesRead:
    try: series = task_series_service.get_task_series(db, workspace_id=workspace_id, series_id=series_id, current_user=current_user)
    except _ERRORS as error: _raise(error)
    return TaskSeriesRead.model_validate(series)


@router.patch("/{series_id}", response_model=TaskSeriesRead)
def update_task_series(workspace_id: uuid.UUID, series_id: uuid.UUID, series_in: TaskSeriesUpdate, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesRead:
    return _write(db, task_series_service.update_task_series, workspace_id=workspace_id, series_id=series_id, current_user=current_user, series_in=series_in)


@router.post("/{series_id}/activate", response_model=TaskSeriesRead)
def activate_task_series(workspace_id: uuid.UUID, series_id: uuid.UUID, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesRead:
    return _write(db, task_series_service.activate_task_series, workspace_id=workspace_id, series_id=series_id, current_user=current_user)


@router.post("/{series_id}/deactivate", response_model=TaskSeriesRead)
def deactivate_task_series(workspace_id: uuid.UUID, series_id: uuid.UUID, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesRead:
    return _write(db, task_series_service.deactivate_task_series, workspace_id=workspace_id, series_id=series_id, current_user=current_user)


@router.post("/{series_id}/materialize", response_model=TaskSeriesMaterializeResponse)
def materialize_one_task_series(workspace_id: uuid.UUID, series_id: uuid.UUID, window: TaskSeriesMaterializeRequest, db: SessionDependency, current_user: CurrentUser) -> TaskSeriesMaterializeResponse:
    return _materialize(db, task_materialization_service.materialize_task_series, workspace_id=workspace_id, series_id=series_id, current_user=current_user, window_start=window.window_start, window_end=window.window_end)
