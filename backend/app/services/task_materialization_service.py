import calendar
import uuid

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.project import Project
from app.models.task import Task
from app.models.task_series import TaskSeries, TaskSeriesFrequency
from app.models.user import User
from app.services.task_series_service import TaskSeriesNotFoundError, TaskSeriesPermissionError
from app.services.workspace import get_workspace_membership


class TaskMaterializationValidationError(ValueError):
    pass


class TaskMaterializationConflictError(ValueError):
    pass


def _validate_window(window_start: datetime, window_end: datetime) -> tuple[datetime, datetime]:
    if window_start.tzinfo is None or window_start.utcoffset() is None or window_end.tzinfo is None or window_end.utcoffset() is None:
        raise TaskMaterializationValidationError("Materialization window must be timezone-aware")
    start = window_start.astimezone(timezone.utc); end = window_end.astimezone(timezone.utc)
    if end < start:
        raise TaskMaterializationValidationError("window_end must be equal to or later than window_start")
    return start, end


def _local_datetime(day: date, anchor: datetime, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(anchor.hour, anchor.minute, anchor.second, anchor.microsecond), tzinfo=zone)


def _candidate_datetimes(series: TaskSeries, window_start: datetime, window_end: datetime) -> list[datetime]:
    zone = ZoneInfo(series.timezone)
    anchor = series.starts_at.astimezone(zone)
    effective_end = min(window_end, series.ends_at.astimezone(timezone.utc)) if series.ends_at else window_end
    if effective_end < window_start or effective_end < series.starts_at.astimezone(timezone.utc):
        return []
    first_date = max(anchor.date(), window_start.astimezone(zone).date())
    last_date = effective_end.astimezone(zone).date()
    candidates: list[datetime] = []

    if series.frequency is TaskSeriesFrequency.DAILY:
        day = first_date
        while day <= last_date:
            delta = (day - anchor.date()).days
            if delta >= 0 and delta % series.interval == 0:
                candidates.append(_local_datetime(day, anchor, zone).astimezone(timezone.utc))
            day += timedelta(days=1)
    elif series.frequency is TaskSeriesFrequency.WEEKLY:
        day = first_date
        anchor_week = anchor.date() - timedelta(days=anchor.weekday())
        weekdays = set(series.weekdays or [])
        while day <= last_date:
            weeks = ((day - timedelta(days=day.weekday())) - anchor_week).days // 7
            if weeks >= 0 and weeks % series.interval == 0 and day.weekday() in weekdays:
                candidates.append(_local_datetime(day, anchor, zone).astimezone(timezone.utc))
            day += timedelta(days=1)
    else:
        start_index = anchor.year * 12 + anchor.month - 1
        end_local = effective_end.astimezone(zone)
        end_index = end_local.year * 12 + end_local.month - 1
        window_local = window_start.astimezone(zone)
        window_index = window_local.year * 12 + window_local.month - 1
        elapsed_months = max(0, window_index - start_index)
        index = start_index + (
            (elapsed_months + series.interval - 1) // series.interval
        ) * series.interval
        while index <= end_index:
            year, month_zero = divmod(index, 12); month = month_zero + 1
            month_day = series.month_day or 1
            if month_day <= calendar.monthrange(year, month)[1]:
                candidates.append(_local_datetime(date(year, month, month_day), anchor, zone).astimezone(timezone.utc))
            index += series.interval

    series_start = series.starts_at.astimezone(timezone.utc)
    return sorted({value for value in candidates if window_start <= value <= effective_end and value >= series_start})


def _validate_associations(db: Session, series: TaskSeries) -> None:
    if series.category_id is not None and db.scalar(select(Category.id).where(Category.id == series.category_id, Category.workspace_id == series.workspace_id)) is None:
        raise TaskMaterializationValidationError("Assigned Category no longer exists")
    if series.project_id is not None and db.scalar(select(Project.id).where(Project.id == series.project_id, Project.workspace_id == series.workspace_id)) is None:
        raise TaskMaterializationValidationError("Assigned Project no longer exists")


def _materialize(db: Session, series: TaskSeries, *, window_start: datetime, window_end: datetime) -> list[Task]:
    if not series.is_active:
        return []
    _validate_associations(db, series)
    candidates = _candidate_datetimes(series, window_start, window_end)
    if not candidates:
        return []
    existing = set(db.scalars(select(Task.scheduled_at).where(Task.task_series_id == series.id, Task.scheduled_at.in_(candidates))).all())
    tasks = [Task(workspace_id=series.workspace_id, created_by_id=series.created_by_id, category_id=series.category_id, project_id=series.project_id, task_series_id=series.id, title=series.title, description=series.description, scheduled_at=value, outcome=None, resolved_at=None) for value in candidates if value not in existing]
    db.add_all(tasks)
    try:
        db.flush()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) != "uq_tasks_task_series_id_scheduled_at":
            raise
        raise TaskMaterializationConflictError("Task occurrences were generated concurrently") from error
    return tasks


def materialize_task_series(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID, current_user: User, window_start: datetime, window_end: datetime) -> list[Task]:
    start, end = _validate_window(window_start, window_end)
    if get_workspace_membership(db, workspace_id=workspace_id, user_id=current_user.id) is None:
        raise TaskSeriesPermissionError("Workspace access denied")
    series = db.scalar(select(TaskSeries).where(TaskSeries.id == series_id, TaskSeries.workspace_id == workspace_id))
    if series is None:
        raise TaskSeriesNotFoundError("Task series not found")
    return _materialize(db, series, window_start=start, window_end=end)


def materialize_workspace_task_series(db: Session, *, workspace_id: uuid.UUID, current_user: User, window_start: datetime, window_end: datetime) -> list[Task]:
    start, end = _validate_window(window_start, window_end)
    if get_workspace_membership(db, workspace_id=workspace_id, user_id=current_user.id) is None:
        raise TaskSeriesPermissionError("Workspace access denied")
    series_items = db.scalars(select(TaskSeries).where(TaskSeries.workspace_id == workspace_id, TaskSeries.is_active.is_(True)).order_by(TaskSeries.id)).all()
    generated: list[Task] = []
    for series in series_items:
        generated.extend(_materialize(db, series, window_start=start, window_end=end))
    return generated
