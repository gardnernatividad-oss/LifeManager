import uuid

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PendingItem, Project, ProjectStep, Task, WorkspaceTrackingMetadata
from app.schemas.home import (
    HomePendingItemAttention,
    HomeProjectStepAttention,
    HomeSummary,
    HomeTaskAttention,
)


def get_home_summary(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_first_name: str,
    local_date: date,
) -> HomeSummary:
    task_row = db.execute(
        select(
            func.count().filter(
                Task.result.is_(None), Task.planned_date == local_date
            ).label("due_today"),
            func.count().filter(
                Task.result.is_(None), Task.planned_date < local_date
            ).label("overdue"),
        ).where(Task.workspace_id == workspace_id)
    ).one()
    pending_row = db.execute(
        select(
            func.count().filter(
                PendingItem.is_active.is_(True),
                PendingItem.progress < 100,
                PendingItem.planned_date < local_date,
            ).label("overdue")
        ).where(PendingItem.workspace_id == workspace_id)
    ).one()
    step_row = db.execute(
        select(
            func.count().filter(
                Project.is_active.is_(True),
                ProjectStep.progress < 100,
                ProjectStep.planned_date < local_date,
            ).label("overdue")
        )
        .select_from(ProjectStep)
        .join(Project)
        .where(Project.workspace_id == workspace_id)
    ).one()
    metadata = db.get(WorkspaceTrackingMetadata, workspace_id)
    return HomeSummary(
        user_first_name=user_first_name,
        local_date=local_date,
        tasks=HomeTaskAttention.model_validate(task_row._mapping),
        pending_items=HomePendingItemAttention.model_validate(pending_row._mapping),
        project_steps=HomeProjectStepAttention.model_validate(step_row._mapping),
        last_review_saved_at=(metadata.last_review_saved_at if metadata else None),
        pending_items_last_tracking_saved_at=(
            metadata.pending_items_last_tracking_saved_at if metadata else None
        ),
    )
