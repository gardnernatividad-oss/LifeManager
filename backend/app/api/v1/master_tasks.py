import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import PersonalWorkspace, SessionDependency
from app.schemas.master_task import (
    MasterTaskCreate,
    MasterTaskListResponse,
    MasterTaskRead,
    MasterTaskUpdate,
)
from app.services import master_task_service


router = APIRouter(prefix="/master-tasks", tags=["Master Tasks"])


def _master_task_error(error: Exception) -> HTTPException:
    if isinstance(error, master_task_service.MasterTaskNotFoundError):
        return HTTPException(status_code=404, detail="Master task not found")
    if isinstance(error, master_task_service.MasterTaskCategoryNotFoundError):
        return HTTPException(status_code=404, detail="Category not found")
    if isinstance(error, master_task_service.MasterTaskNameConflictError):
        return HTTPException(status_code=409, detail="Master task name already exists")
    if isinstance(error, master_task_service.MasterTaskInUseError):
        return HTTPException(status_code=409, detail="Master task is already in use")
    raise error


@router.post("", response_model=MasterTaskRead, status_code=status.HTTP_201_CREATED)
def create_master_task(
    master_task_in: MasterTaskCreate,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> MasterTaskRead:
    try:
        master_task = master_task_service.create_master_task(
            db, workspace_id=workspace.id, master_task_in=master_task_in
        )
        db.commit()
        db.refresh(master_task)
    except (
        master_task_service.MasterTaskCategoryNotFoundError,
        master_task_service.MasterTaskNameConflictError,
    ) as error:
        db.rollback()
        raise _master_task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return MasterTaskRead.model_validate(master_task)


@router.get("", response_model=MasterTaskListResponse)
def list_master_tasks(
    db: SessionDependency,
    workspace: PersonalWorkspace,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    category_id: uuid.UUID | None = None,
) -> MasterTaskListResponse:
    try:
        items, total = master_task_service.list_master_tasks(
            db,
            workspace_id=workspace.id,
            page=page,
            page_size=page_size,
            category_id=category_id,
        )
    except master_task_service.MasterTaskCategoryNotFoundError as error:
        raise _master_task_error(error) from error
    return MasterTaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.patch("/{master_task_id}", response_model=MasterTaskRead)
def update_master_task(
    master_task_id: uuid.UUID,
    master_task_in: MasterTaskUpdate,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> MasterTaskRead:
    try:
        master_task = master_task_service.update_master_task(
            db,
            workspace_id=workspace.id,
            master_task_id=master_task_id,
            master_task_in=master_task_in,
        )
        db.commit()
        db.refresh(master_task)
    except (
        master_task_service.MasterTaskNotFoundError,
        master_task_service.MasterTaskCategoryNotFoundError,
        master_task_service.MasterTaskNameConflictError,
        master_task_service.MasterTaskInUseError,
    ) as error:
        db.rollback()
        raise _master_task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return MasterTaskRead.model_validate(master_task)


@router.delete("/{master_task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_task(
    master_task_id: uuid.UUID,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> Response:
    try:
        master_task_service.delete_master_task(
            db,
            workspace_id=workspace.id,
            master_task_id=master_task_id,
        )
        db.commit()
    except (
        master_task_service.MasterTaskNotFoundError,
        master_task_service.MasterTaskInUseError,
    ) as error:
        db.rollback()
        raise _master_task_error(error) from error
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
