import uuid

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Activity, ActivityMaster, MasterTask, PendingItem, Project, ProjectStage, Task


@dataclass(frozen=True)
class ReportSummaryProjection:
    tasks: int
    pending_items: int
    projects: int
    activities: int

    @property
    def total(self) -> int:
        return self.tasks + self.pending_items + self.projects + self.activities


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
