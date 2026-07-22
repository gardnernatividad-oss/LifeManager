import uuid

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_series import TaskSeries
from app.models.user import User
from app.services.task_materialization_service import (
    _candidate_datetimes,
    _validate_associations,
    _validate_window,
)
from app.services.task_series_service import (
    TaskSeriesNotFoundError,
    TaskSeriesPermissionError,
)
from app.services.workspace import get_workspace_membership


class TaskSeriesSyncInactiveError(ValueError):
    pass


class TaskSeriesSyncConflictError(ValueError):
    pass


@dataclass
class TaskSeriesSyncResult:
    created_tasks: list[Task]
    updated_tasks: list[Task]
    deleted_task_ids: list[uuid.UUID]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def synchronize_task_series(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    series_id: uuid.UUID,
    current_user: User,
    window_start: datetime,
    window_end: datetime,
) -> TaskSeriesSyncResult:
    start, end = _validate_window(window_start, window_end)
    if get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    ) is None:
        raise TaskSeriesPermissionError("Workspace access denied")

    series = db.scalar(
        select(TaskSeries).where(
            TaskSeries.id == series_id,
            TaskSeries.workspace_id == workspace_id,
        )
    )
    if series is None:
        raise TaskSeriesNotFoundError("Task series not found")
    if not series.is_active:
        raise TaskSeriesSyncInactiveError("Task series is inactive")
    _validate_associations(db, series)

    now = _utc_now()
    desired_times = {
        candidate
        for candidate in _candidate_datetimes(series, start, end)
        if candidate > now
    }
    existing = list(
        db.scalars(
            select(Task).where(
                Task.task_series_id == series.id,
                Task.scheduled_at >= start,
                Task.scheduled_at <= end,
            )
        ).all()
    )
    existing_by_time = {task.scheduled_at: task for task in existing}
    mutable = [
        task
        for task in existing
        if task.outcome is None and task.scheduled_at > now
    ]

    deleted = [task for task in mutable if task.scheduled_at not in desired_times]
    deleted_ids = [task.id for task in deleted]
    for task in deleted:
        db.delete(task)
    if deleted:
        db.flush()

    metadata = {
        "title": series.title,
        "description": series.description,
        "category_id": series.category_id,
        "project_id": series.project_id,
    }
    updated: list[Task] = []
    for task in mutable:
        if task.scheduled_at not in desired_times:
            continue
        changed = False
        for field, value in metadata.items():
            if getattr(task, field) != value:
                setattr(task, field, value)
                changed = True
        if changed:
            updated.append(task)

    occupied_times = set(existing_by_time) - {task.scheduled_at for task in deleted}
    created = [
        Task(
            workspace_id=series.workspace_id,
            created_by_id=series.created_by_id,
            category_id=series.category_id,
            project_id=series.project_id,
            task_series_id=series.id,
            title=series.title,
            description=series.description,
            scheduled_at=scheduled_at,
            outcome=None,
            resolved_at=None,
        )
        for scheduled_at in sorted(desired_times - occupied_times)
    ]
    db.add_all(created)
    try:
        db.flush()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) != (
            "uq_tasks_task_series_id_scheduled_at"
        ):
            raise
        raise TaskSeriesSyncConflictError(
            "Task series synchronization conflicted with concurrent generation"
        ) from error

    return TaskSeriesSyncResult(
        created_tasks=created,
        updated_tasks=updated,
        deleted_task_ids=deleted_ids,
    )
