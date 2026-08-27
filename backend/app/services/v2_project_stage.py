import uuid

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Project, ProjectStage, User, WorkspaceMember
from app.models.enums import AccountStatus, MembershipStatus, WorkspaceKind
from app.schemas.v2_project_stage import ProjectStageCreate, ProjectStageUpdate
from app.services.v2_workspace import WorkspaceAccess


class ProjectStageNotFoundError(LookupError):
    pass


class ProjectStageConflictError(ValueError):
    pass


class ProjectStageReferenceUnavailableError(ValueError):
    pass


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint in {"fk_project_stages_project_workspace", "fk_project_stages_responsible_membership"}:
            raise ProjectStageReferenceUnavailableError("Stage reference unavailable") from error
        if constraint == "uq_project_stages_project_position":
            raise ProjectStageConflictError("Stage position conflict") from error
        raise


def _project(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, lock: bool = False) -> Project:
    statement = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise ProjectStageNotFoundError("Project not found")
    return project


def _stage(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID, lock: bool = False) -> ProjectStage:
    statement = select(ProjectStage).where(ProjectStage.id == stage_id, ProjectStage.project_id == project_id, ProjectStage.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    stage = db.scalar(statement)
    if stage is None:
        raise ProjectStageNotFoundError("Stage not found")
    return stage


def _responsible(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> User:
    row = db.execute(select(User, WorkspaceMember).join(WorkspaceMember, WorkspaceMember.user_id == User.id).where(User.id == user_id, User.account_status == AccountStatus.ACTIVE, WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.status == MembershipStatus.ACTIVE).with_for_update()).one_or_none()
    if row is None:
        raise ProjectStageReferenceUnavailableError("Responsible unavailable")
    return row[0]


def _total_weight(db: Session, *, project_id: uuid.UUID, exclude_stage_id: uuid.UUID | None = None) -> Decimal:
    statement = select(func.coalesce(func.sum(ProjectStage.weight), 0)).where(ProjectStage.project_id == project_id)
    if exclude_stage_id is not None:
        statement = statement.where(ProjectStage.id != exclude_stage_id)
    return Decimal(db.scalar(statement) or 0)


def _check_project(project: Project, expected_version: int) -> None:
    if not project.is_active or project.lock_version != expected_version:
        raise ProjectStageConflictError("Project is inactive or stale")


def create_project_stage(db: Session, *, access: WorkspaceAccess, actor: User, project_id: uuid.UUID, stage_in: ProjectStageCreate) -> ProjectStage:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_project(project, stage_in.project_lock_version)
    responsible_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (stage_in.responsible_user_id or actor.id)
    _responsible(db, workspace_id=access.workspace.id, user_id=responsible_id)
    if _total_weight(db, project_id=project.id) + stage_in.weight > Decimal("100"):
        raise ProjectStageConflictError("Total Stage weight exceeds 100")
    stage = ProjectStage(workspace_id=project.workspace_id, project_id=project.id, responsible_user_id=responsible_id, name=stage_in.name, position=stage_in.position, weight=stage_in.weight, planned_date=stage_in.planned_date, progress=0, completion_date=None)
    db.add(stage)
    project.lock_version += 1
    _flush(db)
    return stage


def list_project_stages(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID) -> tuple[Project, list[tuple[ProjectStage, User]]]:
    project = _project(db, workspace_id=workspace_id, project_id=project_id)
    rows = list(db.execute(select(ProjectStage, User).join(User, User.id == ProjectStage.responsible_user_id).where(ProjectStage.workspace_id == workspace_id, ProjectStage.project_id == project_id).order_by(ProjectStage.position, ProjectStage.id)).all())
    return project, rows


def get_project_stage(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, stage_id: uuid.UUID) -> ProjectStage:
    _project(db, workspace_id=workspace_id, project_id=project_id)
    return _stage(db, workspace_id=workspace_id, project_id=project_id, stage_id=stage_id)


def update_project_stage(db: Session, *, access: WorkspaceAccess, project_id: uuid.UUID, stage_id: uuid.UUID, stage_in: ProjectStageUpdate) -> ProjectStage:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_project(project, stage_in.project_lock_version)
    stage = _stage(db, workspace_id=access.workspace.id, project_id=project_id, stage_id=stage_id, lock=True)
    if stage.progress == 100 or stage.lock_version != stage_in.lock_version:
        raise ProjectStageConflictError("Stage is finalized or stale")
    values = stage_in.model_dump(exclude_unset=True, exclude={"lock_version", "project_lock_version"})
    if "responsible_user_id" in values and values["responsible_user_id"] != stage.responsible_user_id:
        _responsible(db, workspace_id=access.workspace.id, user_id=values["responsible_user_id"])
    if "weight" in values and _total_weight(db, project_id=project_id, exclude_stage_id=stage.id) + values["weight"] > Decimal("100"):
        raise ProjectStageConflictError("Total Stage weight exceeds 100")
    for field, value in values.items():
        setattr(stage, field, value)
    stage.lock_version += 1
    project.lock_version += 1
    _flush(db)
    return stage


def update_project_stage_progress(db: Session, *, access: WorkspaceAccess, project_id: uuid.UUID, stage_id: uuid.UUID, progress: int, expected_version: int, project_version: int, local_date: date) -> ProjectStage:
    project = _project(db, workspace_id=access.workspace.id, project_id=project_id, lock=True)
    _check_project(project, project_version)
    stage = _stage(db, workspace_id=access.workspace.id, project_id=project_id, stage_id=stage_id, lock=True)
    if stage.progress == 100 or stage.lock_version != expected_version or stage.progress == progress:
        raise ProjectStageConflictError("Stage progress cannot be changed")
    stage.progress = progress
    stage.completion_date = local_date if progress == 100 else None
    stage.lock_version += 1
    project.lock_version += 1
    _flush(db)
    return stage


def stage_projection(stage: ProjectStage, *, local_date: date) -> tuple[str, str, int, bool]:
    state = "NO_INICIADA" if stage.progress == 0 else "FINALIZADA" if stage.progress == 100 else "EN_PROCESO"
    effective = stage.completion_date or local_date
    if stage.completion_date is None:
        compliance = "EN_PLAZO" if local_date <= stage.planned_date else "ATRASADO"
    elif stage.completion_date == stage.planned_date:
        compliance = "A_TIEMPO"
    elif stage.completion_date < stage.planned_date:
        compliance = "CON_ADELANTO"
    else:
        compliance = "CON_RETRASO"
    return state, compliance, abs((effective - stage.planned_date).days), stage.progress < 100


def project_stage_summary(stages: list[ProjectStage], *, local_date: date) -> dict[str, object]:
    total = sum((stage.weight for stage in stages), Decimal("0"))
    complete_weights = bool(stages) and total == Decimal("100")
    if not stages:
        return {"planned_date": None, "progress": Decimal("0"), "state": "NO_INICIADO", "compliance": None, "compliance_detail_days": None, "completion_date": None, "weights_complete": False, "stage_count": 0, "total_weight": total}
    planned = max(stage.planned_date for stage in stages)
    if not complete_weights:
        return {"planned_date": planned, "progress": None, "state": "CONFIGURACION_INCOMPLETA", "compliance": None, "compliance_detail_days": None, "completion_date": None, "weights_complete": False, "stage_count": len(stages), "total_weight": total}
    progress = sum((Decimal(stage.progress) * stage.weight for stage in stages), Decimal("0")) / Decimal("100")
    state = "NO_INICIADO" if progress == 0 else "FINALIZADO" if progress == 100 else "EN_PROCESO"
    completion = max((stage.completion_date for stage in stages), default=None) if all(stage.completion_date is not None for stage in stages) else None
    effective = completion or local_date
    compliance = "EN_PLAZO" if completion is None and local_date <= planned else "ATRASADO" if completion is None else "A_TIEMPO" if completion == planned else "CON_ADELANTO" if completion < planned else "CON_RETRASO"
    return {"planned_date": planned, "progress": progress, "state": state, "compliance": compliance, "compliance_detail_days": abs((effective - planned).days), "completion_date": completion, "weights_complete": True, "stage_count": len(stages), "total_weight": total}
