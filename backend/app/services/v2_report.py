import uuid

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import String, and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Activity, ActivityMaster, Category, MasterTask, PendingItem, Project, ProjectStage, Task, TaskResult


@dataclass(frozen=True)
class ReportSummaryProjection:
    tasks: int
    pending_items: int
    projects: int
    activities: int

    @property
    def total(self) -> int:
        return self.tasks + self.pending_items + self.projects + self.activities


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _completion_rate(completed: int, resolved: int) -> Decimal | None:
    return None if resolved == 0 else (Decimal(completed) * 100 / Decimal(resolved)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _task_metrics(values) -> dict:
    completed = int(values.completed_count or 0)
    not_completed = int(values.not_completed_count or 0)
    resolved = completed + not_completed
    return {"total_count": int(values.total_count or 0), "pending_count": int(values.pending_count or 0), "completed_count": completed, "not_completed_count": not_completed, "resolved_count": resolved, "completion_rate": _completion_rate(completed, resolved)}


def _task_aggregate_columns():
    return (func.count(Task.id).label("total_count"), func.count(Task.id).filter(Task.result.is_(None)).label("pending_count"), func.count(Task.id).filter(Task.result == TaskResult.COMPLETED).label("completed_count"), func.count(Task.id).filter(Task.result == TaskResult.NOT_COMPLETED).label("not_completed_count"))


def get_task_report(db: Session, *, workspace_id: uuid.UUID, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None, master_task_id: uuid.UUID | None = None, custom_tasks: bool | None = None) -> dict:
    filters = [Task.workspace_id == workspace_id, *_date_filters(Task.planned_date, date_from, date_until)]
    if category_id is not None: filters.append(or_(MasterTask.category_id == category_id, Task.custom_category_id == category_id))
    if responsible_user_id is not None: filters.append(Task.responsible_user_id == responsible_user_id)
    if master_task_id is not None: filters.append(Task.master_task_id == master_task_id)
    if custom_tasks is True: filters.append(Task.master_task_id.is_(None))
    elif custom_tasks is False: filters.append(Task.master_task_id.is_not(None))
    source = Task.__table__.outerjoin(MasterTask, and_(MasterTask.id == Task.master_task_id, MasterTask.workspace_id == Task.workspace_id)).outerjoin(Category, Category.id == func.coalesce(MasterTask.category_id, Task.custom_category_id))
    summary = db.execute(select(*_task_aggregate_columns()).select_from(source).where(*filters)).one()
    task_key = func.coalesce(func.cast(MasterTask.id, String), "CUSTOM")
    task_label = func.coalesce(MasterTask.name, "Otras tareas")
    by_task = db.execute(select(task_key.label("key"), task_label.label("label"), *_task_aggregate_columns()).select_from(source).where(*filters).group_by(task_key, task_label).order_by(task_label, task_key)).all()
    by_category = db.execute(select(func.cast(Category.id, String).label("key"), Category.name.label("label"), *_task_aggregate_columns()).select_from(source).where(*filters).group_by(Category.id, Category.name).order_by(Category.name, Category.id)).all()
    evolution = db.execute(select(Task.planned_date, *_task_aggregate_columns()).select_from(source).where(*filters).group_by(Task.planned_date).order_by(Task.planned_date)).all()
    return {"summary": _task_metrics(summary), "by_task": [{"key": row.key, "label": row.label, **_task_metrics(row)} for row in by_task], "by_category": [{"key": row.key, "label": row.label, **_task_metrics(row)} for row in by_category], "evolution": [{"planned_date": row.planned_date, **_task_metrics(row)} for row in evolution]}


def _compliance_columns(model, local_date: date):
    unfinished = model.completion_date.is_(None)
    return (func.count().filter(unfinished & (model.planned_date >= local_date)).label("en_plazo_count"), func.count().filter(unfinished & (model.planned_date < local_date)).label("atrasado_count"), func.count().filter(model.completion_date < model.planned_date).label("con_adelanto_count"), func.count().filter(model.completion_date == model.planned_date).label("a_tiempo_count"), func.count().filter(model.completion_date > model.planned_date).label("con_retraso_count"))


def _compliance(values) -> dict:
    return {name: int(getattr(values, name) or 0) for name in ("en_plazo_count", "atrasado_count", "con_adelanto_count", "a_tiempo_count", "con_retraso_count")}


def _progress_metrics(values) -> dict:
    return {"total_count": int(values.total_count or 0), "no_iniciado_count": int(values.no_iniciado_count or 0), "en_proceso_count": int(values.en_proceso_count or 0), "finalizado_count": int(values.finalizado_count or 0), "configuracion_incompleta_count": int(getattr(values, "configuracion_incompleta_count", 0) or 0), "average_progress": _decimal(values.average_progress)}


def _progress_columns(model):
    return (func.count(model.id).label("total_count"), func.count(model.id).filter(model.progress == 0).label("no_iniciado_count"), func.count(model.id).filter(model.progress.between(1, Decimal("99.99"))).label("en_proceso_count"), func.count(model.id).filter(model.progress == 100).label("finalizado_count"), func.avg(model.progress).label("average_progress"))


def get_pending_item_report(db: Session, *, workspace_id: uuid.UUID, local_date: date, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None) -> dict:
    filters = [PendingItem.workspace_id == workspace_id, *_date_filters(PendingItem.planned_date, date_from, date_until)]
    if category_id is not None: filters.append(PendingItem.category_id == category_id)
    if responsible_user_id is not None: filters.append(PendingItem.responsible_user_id == responsible_user_id)
    source = PendingItem.__table__.join(Category, Category.id == PendingItem.category_id)
    summary = db.execute(select(*_progress_columns(PendingItem), *_compliance_columns(PendingItem, local_date)).select_from(source).where(*filters)).one()
    categories = db.execute(select(Category.id.label("category_id"), Category.name.label("category_name"), *_progress_columns(PendingItem)).select_from(source).where(*filters).group_by(Category.id, Category.name).order_by(Category.name, Category.id)).all()
    evolution = db.execute(select(PendingItem.planned_date, func.count(PendingItem.id).label("total_count"), func.avg(PendingItem.progress).label("average_progress")).where(*filters, PendingItem.planned_date.is_not(None)).group_by(PendingItem.planned_date).order_by(PendingItem.planned_date)).all()
    return {"summary": _progress_metrics(summary), "compliance": _compliance(summary), "by_category": [{"category_id": row.category_id, "category_name": row.category_name, **_progress_metrics(row)} for row in categories], "evolution": [{"planned_date": row.planned_date, "total_count": int(row.total_count), "average_progress": _decimal(row.average_progress)} for row in evolution]}


def _project_population(workspace_id: uuid.UUID, category_id: uuid.UUID | None, responsible_user_id: uuid.UUID | None):
    filters = [Project.workspace_id == workspace_id]
    if category_id is not None: filters.append(Project.category_id == category_id)
    if responsible_user_id is not None: filters.append(Project.leader_user_id == responsible_user_id)
    return select(Project.id.label("project_id"), Project.name.label("project_name"), Project.category_id, Category.name.label("category_name"), func.count(ProjectStage.id).label("stage_count"), func.max(ProjectStage.planned_date).label("planned_date"), func.coalesce(func.sum(ProjectStage.weight), 0).label("total_weight"), func.coalesce(func.sum(ProjectStage.weight * ProjectStage.progress), 0).label("weighted_sum"), func.min(ProjectStage.progress).label("minimum_progress"), func.max(ProjectStage.progress).label("maximum_progress")).select_from(Project).join(Category, Category.id == Project.category_id).outerjoin(ProjectStage, and_(ProjectStage.project_id == Project.id, ProjectStage.workspace_id == Project.workspace_id)).where(*filters).group_by(Project.id, Project.name, Project.category_id, Category.name).subquery()


def get_project_report(db: Session, *, workspace_id: uuid.UUID, local_date: date, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None) -> dict:
    projects = _project_population(workspace_id, category_id, responsible_user_id)
    complete = and_(projects.c.stage_count > 0, projects.c.total_weight == Decimal("100.00"))
    progress = case((complete, projects.c.weighted_sum / Decimal("100.00")), else_=None)
    state = case((~complete, "CONFIGURACION_INCOMPLETA"), (projects.c.maximum_progress == 0, "NO_INICIADO"), (projects.c.minimum_progress == 100, "FINALIZADO"), else_="EN_PROCESO")
    population = select(projects, progress.label("progress"), state.label("state")).where(*_date_filters(projects.c.planned_date, date_from, date_until)).subquery()
    summary = db.execute(select(func.count(population.c.project_id).label("total_count"), func.count().filter(population.c.state == "NO_INICIADO").label("no_iniciado_count"), func.count().filter(population.c.state == "EN_PROCESO").label("en_proceso_count"), func.count().filter(population.c.state == "FINALIZADO").label("finalizado_count"), func.count().filter(population.c.state == "CONFIGURACION_INCOMPLETA").label("configuracion_incompleta_count"), func.avg(population.c.progress).label("average_progress"))).one()
    rows = db.execute(select(population).order_by(population.c.planned_date.asc().nulls_last(), population.c.project_name, population.c.project_id)).all()
    categories = db.execute(select(population.c.category_id, population.c.category_name, func.count(population.c.project_id).label("total_count"), func.count().filter(population.c.state == "NO_INICIADO").label("no_iniciado_count"), func.count().filter(population.c.state == "EN_PROCESO").label("en_proceso_count"), func.count().filter(population.c.state == "FINALIZADO").label("finalizado_count"), func.count().filter(population.c.state == "CONFIGURACION_INCOMPLETA").label("configuracion_incompleta_count"), func.avg(population.c.progress).label("average_progress")).group_by(population.c.category_id, population.c.category_name).order_by(population.c.category_name, population.c.category_id)).all()
    compliance = db.execute(select(*_compliance_columns(ProjectStage, local_date)).where(ProjectStage.workspace_id == workspace_id, ProjectStage.project_id.in_(select(population.c.project_id)))).one()
    evolution = db.execute(select(population.c.planned_date, func.count(population.c.project_id).label("total_count"), func.avg(population.c.progress).label("average_progress")).where(population.c.planned_date.is_not(None)).group_by(population.c.planned_date).order_by(population.c.planned_date)).all()
    return {"summary": _progress_metrics(summary), "stage_compliance": _compliance(compliance), "by_category": [{"category_id": row.category_id, "category_name": row.category_name, **_progress_metrics(row)} for row in categories], "by_project": [{"project_id": row.project_id, "project_name": row.project_name, "category_id": row.category_id, "category_name": row.category_name, "planned_date": row.planned_date, "progress": _decimal(row.progress), "state": row.state, "stage_count": int(row.stage_count)} for row in rows], "evolution": [{"planned_date": row.planned_date, "total_count": int(row.total_count), "average_progress": _decimal(row.average_progress)} for row in evolution]}


def _date_filters(column, date_from: date | None, date_until: date | None):
    filters = []
    if date_from is not None:
        filters.append(column >= date_from)
    if date_until is not None:
        filters.append(column <= date_until)
    return filters


def get_report_summary(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    timezone_name: str,
    date_from: date | None = None,
    date_until: date | None = None,
    category_id: uuid.UUID | None = None,
    responsible_user_id: uuid.UUID | None = None,
) -> ReportSummaryProjection:
    """Return bounded Workspace aggregates without loading domain rows."""
    task_filters = [Task.workspace_id == workspace_id, *_date_filters(Task.planned_date, date_from, date_until)]
    pending_filters = [PendingItem.workspace_id == workspace_id, *_date_filters(PendingItem.planned_date, date_from, date_until)]
    project_filters = [Project.workspace_id == workspace_id]
    activity_filters = [Activity.workspace_id == workspace_id]

    if category_id is not None:
        task_filters.append(or_(MasterTask.category_id == category_id, Task.custom_category_id == category_id))
        pending_filters.append(PendingItem.category_id == category_id)
        project_filters.append(Project.category_id == category_id)
        activity_filters.append(or_(ActivityMaster.category_id == category_id, Activity.custom_category_id == category_id))
    if responsible_user_id is not None:
        task_filters.append(Task.responsible_user_id == responsible_user_id)
        pending_filters.append(PendingItem.responsible_user_id == responsible_user_id)
        project_filters.append(Project.leader_user_id == responsible_user_id)
        activity_filters.append(Activity.organizer_user_id == responsible_user_id)

    project_dates = (
        select(
            Project.id.label("project_id"),
            func.max(ProjectStage.planned_date).label("planned_date"),
        )
        .select_from(Project)
        .outerjoin(
            ProjectStage,
            and_(ProjectStage.project_id == Project.id, ProjectStage.workspace_id == Project.workspace_id),
        )
        .where(*project_filters)
        .group_by(Project.id)
        .subquery()
    )
    project_count_filters = _date_filters(project_dates.c.planned_date, date_from, date_until)

    zone = ZoneInfo(timezone_name)
    if date_from is not None:
        activity_filters.append(Activity.starts_at >= datetime.combine(date_from, time.min, zone))
    if date_until is not None:
        activity_filters.append(Activity.starts_at < datetime.combine(date_until + timedelta(days=1), time.min, zone))

    statement = select(
        select(func.count(Task.id))
        .select_from(Task)
        .outerjoin(MasterTask, and_(MasterTask.id == Task.master_task_id, MasterTask.workspace_id == Task.workspace_id))
        .where(*task_filters)
        .scalar_subquery()
        .label("tasks"),
        select(func.count(PendingItem.id)).where(*pending_filters).scalar_subquery().label("pending_items"),
        select(func.count(project_dates.c.project_id))
        .where(*project_count_filters)
        .scalar_subquery()
        .label("projects"),
        select(func.count(Activity.id))
        .select_from(Activity)
        .outerjoin(
            ActivityMaster,
            and_(ActivityMaster.id == Activity.activity_master_id, ActivityMaster.workspace_id == Activity.workspace_id),
        )
        .where(*activity_filters)
        .scalar_subquery()
        .label("activities"),
    )
    row = db.execute(statement).one()
    return ReportSummaryProjection(
        tasks=int(row.tasks or 0),
        pending_items=int(row.pending_items or 0),
        projects=int(row.projects or 0),
        activities=int(row.activities or 0),
    )
