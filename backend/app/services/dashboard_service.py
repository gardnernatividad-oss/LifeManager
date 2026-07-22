import uuid

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskOutcome
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services.workspace import get_workspace_membership


class DashboardPermissionError(PermissionError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_dashboard_summary(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
) -> DashboardSummary:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise DashboardPermissionError("Workspace access denied")

    now = _utc_now()
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)
    next_seven_days = now + timedelta(days=7)
    unresolved = Task.outcome.is_(None)

    statement = select(
        func.count().filter(unresolved, Task.scheduled_at <= now).label("pending_tasks"),
        func.count().filter(unresolved, Task.scheduled_at > now).label("scheduled_tasks"),
        func.count().filter(Task.outcome == TaskOutcome.COMPLETED).label("completed_tasks"),
        func.count().filter(Task.outcome == TaskOutcome.NOT_COMPLETED).label("not_completed_tasks"),
        func.count().filter(Task.outcome == TaskOutcome.CANCELLED).label("cancelled_tasks"),
        func.count().label("total_tasks"),
        func.count().filter(
            unresolved,
            Task.scheduled_at >= today_start,
            Task.scheduled_at < tomorrow_start,
        ).label("tasks_due_today"),
        func.count().filter(
            unresolved,
            Task.scheduled_at >= now,
            Task.scheduled_at < next_seven_days,
        ).label("tasks_due_next_7_days"),
        func.count().filter(unresolved, Task.scheduled_at < now).label("overdue_tasks"),
    ).where(Task.workspace_id == workspace_id)

    row = db.execute(statement).one()
    return DashboardSummary.model_validate(row._mapping)
