import uuid

from decimal import Decimal
from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.models import Project, ProjectStage, User
from app.schemas.v2_project_stage import ProjectStageConfiguration, ProjectStageCorrection, ProjectStageCreate, ProjectStageHistoryListResponse, ProjectStageHistoryRead, ProjectStageListResponse, ProjectStageProgress, ProjectStageRead, ProjectStageReorder, ProjectStageUpdate
from app.services.v2_project_stage import ProjectStageConflictError, ProjectStageNotFoundError, ProjectStageReferenceUnavailableError, configure_project_stages, correct_project_stage_progress, create_project_stage, get_project_stage, list_project_stage_history, list_project_stages, reorder_project_stages, stage_projection, update_project_stage, update_project_stage_progress


router = APIRouter(prefix="/workspaces/{workspace_id}/projects/{project_id}/stages", tags=["V2 Project Stages"])


def _raise(error: Exception) -> None:
    if isinstance(error, (ProjectStageNotFoundError, ProjectStageReferenceUnavailableError)):
        raise V2APIError(status_code=404, code="PROJECT_STAGE_NOT_FOUND", message="No se encontró la Etapa o una referencia disponible.") from error
    raise V2APIError(status_code=409, code="PROJECT_STAGE_CONFLICT", message="La Etapa cambió o no admite esta acción.") from error


def _write(db: SessionDependency, operation):
    try:
        result = operation()
        db.commit()
        db.refresh(result)
        return result
    except (ProjectStageNotFoundError, ProjectStageConflictError, ProjectStageReferenceUnavailableError) as error:
        db.rollback()
        _raise(error)
    except Exception:
        db.rollback()
        raise


def _write_many(db: SessionDependency, operation):
    try:
        result = operation()
        db.commit()
        for stage in result:
            db.refresh(stage)
        return result
    except (ProjectStageNotFoundError, ProjectStageConflictError, ProjectStageReferenceUnavailableError) as error:
        db.rollback()
        _raise(error)
    except Exception:
        db.rollback()
        raise


def _read(db: SessionDependency, stage: ProjectStage, *, today, responsible: User | None = None, project_active: bool | None = None) -> ProjectStageRead:
    responsible = responsible or db.scalar(select(User).where(User.id == stage.responsible_user_id))
    if responsible is None:
        raise V2APIError(status_code=404, code="PROJECT_STAGE_NOT_FOUND", message="No se encontró la Etapa.")
    if project_active is None:
        project_active = bool(db.scalar(select(Project.is_active).where(Project.id == stage.project_id, Project.workspace_id == stage.workspace_id)))
    state, compliance, detail, mutable = stage_projection(stage, local_date=today)
    mutable = mutable and project_active
    return ProjectStageRead(id=stage.id, workspace_id=stage.workspace_id, project_id=stage.project_id, responsible_user_id=stage.responsible_user_id, responsible_display_name=f"{responsible.first_name} {responsible.last_name}".strip(), responsible_email=responsible.email, name=stage.name, position=stage.position, weight=stage.weight, planned_date=stage.planned_date, progress=stage.progress, state=state, completion_date=stage.completion_date, compliance=compliance, compliance_detail_days=detail, lock_version=stage.lock_version, can_edit=mutable, can_update_progress=mutable, can_correct_progress=bool(project_active and not mutable), created_at=stage.created_at, updated_at=stage.updated_at)


def _list_read(db: SessionDependency, project: Project, stages: list[ProjectStage], *, today) -> ProjectStageListResponse:
    total = sum((stage.weight for stage in stages), start=Decimal("0.00"))
    return ProjectStageListResponse(items=[_read(db, stage, today=today, project_active=project.is_active) for stage in stages], total_weight=total, weights_complete=bool(stages) and total == Decimal("100.00"))


@router.get("", response_model=ProjectStageListResponse)
def index(workspace_id: uuid.UUID, project_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageListResponse:
    del access
    try:
        project, rows = list_project_stages(db, workspace_id=workspace_id, project_id=project_id)
    except ProjectStageNotFoundError as error:
        _raise(error)
    total = sum((stage.weight for stage, _ in rows), start=Decimal("0"))
    return ProjectStageListResponse(items=[_read(db, stage, today=local_today(account.timezone), responsible=responsible, project_active=project.is_active) for stage, responsible in rows], total_weight=total, weights_complete=bool(rows) and total == Decimal("100"))


@router.post("", response_model=ProjectStageRead, status_code=status.HTTP_201_CREATED)
def create(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_in: ProjectStageCreate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageRead:
    del workspace_id
    return _read(db, _write(db, lambda: create_project_stage(db, access=access, actor=account, project_id=project_id, stage_in=stage_in)), today=local_today(account.timezone))


@router.put("/configuration", response_model=ProjectStageListResponse)
def configuration(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_in: ProjectStageConfiguration, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageListResponse:
    del workspace_id
    stages = _write_many(db, lambda: configure_project_stages(db, access=access, actor=account, project_id=project_id, configuration_in=stage_in))
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == access.workspace.id))
    if project is None:
        raise V2APIError(status_code=404, code="PROJECT_STAGE_NOT_FOUND", message="No se encontró el Proyecto.")
    return _list_read(db, project, stages, today=local_today(account.timezone))


@router.post("/reorder", response_model=ProjectStageListResponse)
def reorder(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_in: ProjectStageReorder, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageListResponse:
    del workspace_id
    stages = _write_many(db, lambda: reorder_project_stages(db, access=access, project_id=project_id, reorder_in=stage_in))
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == access.workspace.id))
    if project is None:
        raise V2APIError(status_code=404, code="PROJECT_STAGE_NOT_FOUND", message="No se encontró el Proyecto.")
    return _list_read(db, project, stages, today=local_today(account.timezone))


@router.get("/{stage_id}", response_model=ProjectStageRead)
def detail(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageRead:
    del access
    try:
        return _read(db, get_project_stage(db, workspace_id=workspace_id, project_id=project_id, stage_id=stage_id), today=local_today(account.timezone))
    except ProjectStageNotFoundError as error:
        _raise(error)


@router.get("/{stage_id}/history", response_model=ProjectStageHistoryListResponse)
def history(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageHistoryListResponse:
    del access
    try:
        rows = list_project_stage_history(db, workspace_id=workspace_id, project_id=project_id, stage_id=stage_id)
    except ProjectStageNotFoundError as error:
        _raise(error)
    return ProjectStageHistoryListResponse(items=[ProjectStageHistoryRead(id=entry.id, previous_progress=entry.previous_progress, progress=entry.progress, comment=entry.comment, type=entry.event_type, actor_user_id=actor.id, actor_display_name=f"{actor.first_name} {actor.last_name}".strip(), recorded_at=entry.recorded_at) for entry, actor in rows])


@router.patch("/{stage_id}", response_model=ProjectStageRead)
def patch(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, stage_in: ProjectStageUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageRead:
    del workspace_id
    return _read(db, _write(db, lambda: update_project_stage(db, access=access, project_id=project_id, stage_id=stage_id, stage_in=stage_in)), today=local_today(account.timezone))


@router.post("/{stage_id}/progress", response_model=ProjectStageRead)
def progress(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, stage_in: ProjectStageProgress, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageRead:
    del workspace_id
    today = local_today(account.timezone)
    return _read(db, _write(db, lambda: update_project_stage_progress(db, access=access, actor=account, project_id=project_id, stage_id=stage_id, progress=stage_in.progress, comment=stage_in.comment, expected_version=stage_in.lock_version, project_version=stage_in.project_lock_version, local_date=today)), today=today)


@router.post("/{stage_id}/correction", response_model=ProjectStageRead)
def correction(workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, stage_in: ProjectStageCorrection, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ProjectStageRead:
    del workspace_id
    return _read(db, _write(db, lambda: correct_project_stage_progress(db, access=access, actor=account, project_id=project_id, stage_id=stage_id, progress=stage_in.progress, comment=stage_in.comment, expected_version=stage_in.lock_version, project_version=stage_in.project_lock_version)), today=local_today(account.timezone))
