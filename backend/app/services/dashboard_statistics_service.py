import uuid

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskOutcome
from app.models.user import User
from app.schemas.dashboard import DashboardStatistics
from app.services.workspace import get_workspace_membership


class DashboardStatisticsPermissionError(PermissionError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_dashboard_statistics(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
) -> DashboardStatistics:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise DashboardStatisticsPermissionError("Workspace access denied")

    now = _utc_now()
    unresolved = Task.outcome.is_(None)
    statement = select(
        func.count().filter(Task.outcome == TaskOutcome.COMPLETED).label("completed_tasks"),
        func.count().filter(Task.outcome == TaskOutcome.NOT_COMPLETED).label("not_completed_tasks"),
        func.count().filter(Task.outcome == TaskOutcome.CANCELLED).label("cancelled_tasks"),
        func.count().filter(Task.outcome.is_not(None)).label("resolved_tasks"),
        func.count().filter(unresolved, Task.scheduled_at <= now).label("pending_tasks"),
        func.count().filter(unresolved, Task.scheduled_at > now).label("scheduled_tasks"),
    ).where(Task.workspace_id == workspace_id)

    values = dict(db.execute(statement).one()._mapping)
    resolved_tasks = int(values["resolved_tasks"])
    completed_tasks = int(values["completed_tasks"])
    values["completion_rate"] = (
        round(completed_tasks / resolved_tasks * 100, 2)
        if resolved_tasks
        else 0.0
    )
    return DashboardStatistics.model_validate(values)
