import uuid

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailRead,
    ProjectGeneralTrackingUpdate,
    ProjectListResponse,
    ProjectPlanningUpdate,
    ProjectRead,
    ProjectState,
    ProjectStepCreate,
    ProjectStepPlanningUpdate,
    ProjectStepRead,
    ProjectTrackingBatch,
    ProjectTrackingBatchResponse,
)
from app.services import project_service


router = APIRouter(prefix="/projects", tags=["Projects"])

_DOMAIN_ERRORS = (
    project_service.ProjectNotFoundError,
    project_service.ProjectStepNotFoundError,
    project_service.ProjectCategoryNotFoundError,
    project_service.ProjectConflictError,
    project_service.ProjectVersionConflictError,
)


def _error(error: Exception) -> HTTPException:
    if isinstance(
        error,
        (
            project_service.ProjectNotFoundError,
            project_service.ProjectStepNotFoundError,
            project_service.ProjectCategoryNotFoundError,
        ),
    ):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


def _today(current_user: CurrentUser) -> date:
    return local_today(current_user.timezone)


@router.post("", response_model=ProjectDetailRead, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectDetailRead:
    today = _today(current_user)
    try:
        project = project_service.create_project(
            db, workspace_id=workspace.id, current_user=current_user,
            project_in=project_in,
        )
        db.commit()
        db.refresh(project)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectDetailRead.from_project(project, local_date=today)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    is_active: bool | None = None,
    category_id: uuid.UUID | None = None,
    state: ProjectState | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
) -> ProjectListResponse:
    try:
        projects, total = project_service.list_projects(
            db, workspace_id=workspace.id, page=page, page_size=page_size,
            is_active=is_active, category_id=category_id, state=state,
            planned_from=planned_from, planned_to=planned_to,
        )
    except _DOMAIN_ERRORS as error:
        raise _error(error) from error
    return ProjectListResponse(
        items=[ProjectRead.from_project(project) for project in projects],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.patch("/{project_id}/tracking-general", response_model=ProjectRead)
def update_project_general_tracking(
    project_id: uuid.UUID,
    project_in: ProjectGeneralTrackingUpdate,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> ProjectRead:
    try:
        project = project_service.update_project_general_tracking(
            db, workspace_id=workspace.id, project_id=project_id,
            project_in=project_in,
        )
        db.commit()
        db.refresh(project)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectRead.from_project(project)


@router.patch("/{project_id}/tracking", response_model=ProjectTrackingBatchResponse)
def save_project_tracking(
    project_id: uuid.UUID,
    tracking_in: ProjectTrackingBatch,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectTrackingBatchResponse:
    today = _today(current_user)
    try:
        project, saved_at = project_service.save_project_tracking(
            db, workspace_id=workspace.id, project_id=project_id,
            tracking_in=tracking_in, local_date=today,
        )
        db.commit()
        db.refresh(project)
        for step in project.steps:
            db.refresh(step)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectTrackingBatchResponse(
        project=ProjectDetailRead.from_project(project, local_date=today),
        saved_at=saved_at,
    )


@router.post(
    "/{project_id}/steps", response_model=ProjectStepRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_step(
    project_id: uuid.UUID,
    step_in: ProjectStepCreate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectStepRead:
    try:
        step = project_service.create_project_step(
            db, workspace_id=workspace.id, project_id=project_id, step_in=step_in
        )
        db.commit()
        db.refresh(step)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectStepRead.from_step(step, local_date=_today(current_user))


@router.patch("/{project_id}/steps/{step_id}", response_model=ProjectStepRead)
def update_project_step(
    project_id: uuid.UUID,
    step_id: uuid.UUID,
    step_in: ProjectStepPlanningUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectStepRead:
    try:
        step = project_service.update_project_step(
            db, workspace_id=workspace.id, project_id=project_id,
            step_id=step_id, step_in=step_in,
        )
        db.commit()
        db.refresh(step)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectStepRead.from_step(step, local_date=_today(current_user))


@router.get("/{project_id}", response_model=ProjectDetailRead)
def get_project(
    project_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectDetailRead:
    try:
        project = project_service.get_project(
            db, workspace_id=workspace.id, project_id=project_id
        )
    except _DOMAIN_ERRORS as error:
        raise _error(error) from error
    return ProjectDetailRead.from_project(project, local_date=_today(current_user))


@router.patch("/{project_id}", response_model=ProjectDetailRead)
def update_project(
    project_id: uuid.UUID,
    project_in: ProjectPlanningUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ProjectDetailRead:
    today = _today(current_user)
    try:
        project = project_service.update_project(
            db, workspace_id=workspace.id, project_id=project_id,
            project_in=project_in,
        )
        db.commit()
        db.refresh(project)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ProjectDetailRead.from_project(project, local_date=today)
