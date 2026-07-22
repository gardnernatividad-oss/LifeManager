import uuid

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task_series import TaskSeries
from app.models.user import User
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.services import task_materialization_service
from app.services.task_series_service import TaskSeriesPermissionError
from app.services.workspace import get_workspace_membership


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _series_day_window(series: TaskSeries, generation_date: date) -> tuple[datetime, datetime]:
    zone = ZoneInfo(series.timezone)
    start = datetime.combine(generation_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(generation_date, time.max, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def generate_daily_tasks(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    generation_date: date,
    current_user: User,
) -> DailyTaskGenerationResponse:
    if get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    ) is None:
        raise TaskSeriesPermissionError("Workspace access denied")

    series_items = db.scalars(
        select(TaskSeries)
        .where(
            TaskSeries.workspace_id == workspace_id,
            TaskSeries.is_active.is_(True),
        )
        .order_by(TaskSeries.id)
    ).all()

    eligible_count = 0
    skipped_count = 0
    created_tasks = []
    for series in series_items:
        window_start, window_end = _series_day_window(series, generation_date)
        candidates = task_materialization_service._candidate_datetimes(
            series,
            window_start,
            window_end,
        )
        if not candidates:
            continue
        eligible_count += 1
        tasks = task_materialization_service._materialize(
            db,
            series,
            window_start=window_start,
            window_end=window_end,
        )
        if tasks:
            created_tasks.extend(tasks)
        else:
            skipped_count += 1

    created_tasks.sort(key=lambda task: (task.scheduled_at, task.task_series_id, task.id))
    return DailyTaskGenerationResponse(
        workspace_id=workspace_id,
        generation_date=generation_date,
        eligible_series_count=eligible_count,
        created_task_count=len(created_tasks),
        skipped_existing_count=skipped_count,
        created_task_ids=[task.id for task in created_tasks],
        generated_at=_utc_now(),
    )
