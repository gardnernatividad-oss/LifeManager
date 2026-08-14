import uuid

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models import (
    PendingItem,
    Project,
    ProjectStep,
    Task,
    User,
    WorkspaceTrackingMetadata,
)
from app.schemas.review import ReviewSave


class ReviewNotFoundError(LookupError):
    pass


class ReviewConflictError(ValueError):
    pass


class ReviewVersionConflictError(ValueError):
    pass


def get_review(
    db: Session, *, workspace_id: uuid.UUID, local_date: date
) -> tuple[list[Task], list[PendingItem], list[ProjectStep], datetime | None]:
    tasks = list(
        db.scalars(
            select(Task)
            .options(selectinload(Task.master_task))
            .where(
                Task.workspace_id == workspace_id,
                Task.result.is_(None),
                Task.planned_date <= local_date,
            )
            .order_by(Task.planned_date, Task.id)
        ).all()
    )
    pending_items = list(
        db.scalars(
            select(PendingItem)
            .where(
                PendingItem.workspace_id == workspace_id,
                PendingItem.is_active.is_(True),
                PendingItem.progress < 100,
                PendingItem.planned_date <= local_date,
            )
            .order_by(PendingItem.planned_date, PendingItem.id)
        ).all()
    )
    project_steps = list(
        db.scalars(
            select(ProjectStep)
            .join(Project)
            .options(selectinload(ProjectStep.project))
            .where(
                Project.workspace_id == workspace_id,
                Project.is_active.is_(True),
                ProjectStep.progress < 100,
                ProjectStep.planned_date <= local_date,
            )
            .order_by(Project.name, Project.id, ProjectStep.position, ProjectStep.id)
        ).all()
    )
    metadata = db.get(WorkspaceTrackingMetadata, workspace_id)
    return (
        tasks,
        pending_items,
        project_steps,
        metadata.last_review_saved_at if metadata is not None else None,
    )


def _lock_tasks(
    db: Session, *, workspace_id: uuid.UUID, review_in: ReviewSave, local_date: date
) -> list[Task]:
    expected = {row.id: row for row in review_in.tasks}
    if not expected:
        return []
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.workspace_id == workspace_id, Task.id.in_(expected))
            .order_by(Task.id)
            .with_for_update()
        ).all()
    )
    if len(tasks) != len(expected):
        raise ReviewNotFoundError("One or more Review Tasks were not found")
    if any(task.lock_version != expected[task.id].lock_version for task in tasks):
        raise ReviewVersionConflictError("One or more Review Task versions are stale")
    if any(task.result is not None or task.planned_date > local_date for task in tasks):
        raise ReviewConflictError("One or more Tasks are not eligible for Review")
    return tasks


def _lock_pending_items(
    db: Session, *, workspace_id: uuid.UUID, review_in: ReviewSave, local_date: date
) -> list[PendingItem]:
    expected = {row.id: row for row in review_in.pending_items}
    if not expected:
        return []
    items = list(
        db.scalars(
            select(PendingItem)
            .where(PendingItem.workspace_id == workspace_id, PendingItem.id.in_(expected))
            .order_by(PendingItem.id)
            .with_for_update()
        ).all()
    )
    if len(items) != len(expected):
        raise ReviewNotFoundError("One or more Review Pending Items were not found")
    if any(item.lock_version != expected[item.id].lock_version for item in items):
        raise ReviewVersionConflictError(
            "One or more Review Pending Item versions are stale"
        )
    if any(
        not item.is_active or item.progress == 100
        or item.planned_date is None or item.planned_date > local_date
        for item in items
    ):
        raise ReviewConflictError("One or more Pending Items are not eligible for Review")
    return items


def _lock_project_steps(
    db: Session, *, workspace_id: uuid.UUID, review_in: ReviewSave, local_date: date
) -> list[ProjectStep]:
    expected = {row.id: row for row in review_in.project_steps}
    if not expected:
        return []
    identified_steps = list(
        db.execute(
            select(ProjectStep.id, ProjectStep.project_id)
            .join(Project)
            .where(
                Project.workspace_id == workspace_id,
                ProjectStep.id.in_(expected),
            )
            .order_by(ProjectStep.id)
        ).all()
    )
    if len(identified_steps) != len(expected):
        raise ReviewNotFoundError("One or more Review Project Steps were not found")
    project_ids = sorted({row.project_id for row in identified_steps}, key=str)
    projects = list(
        db.scalars(
            select(Project)
            .where(Project.workspace_id == workspace_id, Project.id.in_(project_ids))
            .order_by(Project.id)
            .with_for_update()
        ).all()
    )
    if len(projects) != len(project_ids):
        raise ReviewNotFoundError("One or more Review Projects were not found")
    active_projects = {project.id for project in projects if project.is_active}
    if active_projects != set(project_ids):
        raise ReviewConflictError("One or more Project Steps are not eligible for Review")
    steps = list(
        db.scalars(
            select(ProjectStep)
            .where(
                ProjectStep.project_id.in_(project_ids),
                ProjectStep.id.in_(expected),
            )
            .order_by(ProjectStep.project_id, ProjectStep.id)
            .with_for_update()
        ).all()
    )
    if len(steps) != len(expected):
        raise ReviewNotFoundError("One or more Review Project Steps were not found")
    if any(step.project_id not in active_projects for step in steps):
        raise ReviewNotFoundError("One or more Review Project Steps were not found")
    if any(step.lock_version != expected[step.id].lock_version for step in steps):
        raise ReviewVersionConflictError(
            "One or more Review Project Step versions are stale"
        )
    if any(
        step.progress == 100 or step.planned_date is None or step.planned_date > local_date
        for step in steps
    ):
        raise ReviewConflictError("One or more Project Steps are not eligible for Review")
    return steps


def save_review(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    local_date: date,
    review_in: ReviewSave,
    saved_at: datetime | None = None,
) -> datetime:
    tasks = _lock_tasks(
        db, workspace_id=workspace_id, review_in=review_in, local_date=local_date
    )
    pending_items = _lock_pending_items(
        db, workspace_id=workspace_id, review_in=review_in, local_date=local_date
    )
    project_steps = _lock_project_steps(
        db, workspace_id=workspace_id, review_in=review_in, local_date=local_date
    )
    task_updates = {row.id: row for row in review_in.tasks}
    pending_updates = {row.id: row for row in review_in.pending_items}
    step_updates = {row.id: row for row in review_in.project_steps}
    timestamp = saved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("saved_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)

    for task in tasks:
        row = task_updates[task.id]
        result = db.execute(
            update(Task)
            .where(
                Task.id == task.id,
                Task.workspace_id == workspace_id,
                Task.lock_version == row.lock_version,
                Task.result.is_(None),
                Task.planned_date <= local_date,
            )
            .values(
                result=row.result,
                resolved_at=timestamp,
                resolved_by_id=current_user.id,
                lock_version=Task.lock_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ReviewVersionConflictError("One or more Review Task versions are stale")

    for item in pending_items:
        row = pending_updates[item.id]
        changes = row.model_dump(exclude_unset=True, exclude={"id", "lock_version"})
        if "progress" in changes:
            if changes["progress"] == 100 and item.progress < 100:
                changes["completion_date"] = local_date
            elif changes["progress"] < 100:
                changes["completion_date"] = None
        result = db.execute(
            update(PendingItem)
            .where(
                PendingItem.id == item.id,
                PendingItem.workspace_id == workspace_id,
                PendingItem.lock_version == row.lock_version,
                PendingItem.is_active.is_(True),
                PendingItem.progress < 100,
                PendingItem.planned_date <= local_date,
            )
            .values(**changes, lock_version=PendingItem.lock_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ReviewVersionConflictError(
                "One or more Review Pending Item versions are stale"
            )

    for step in project_steps:
        row = step_updates[step.id]
        changes = row.model_dump(exclude_unset=True, exclude={"id", "lock_version"})
        if "progress" in changes:
            if changes["progress"] == 100 and step.progress < 100:
                changes["completion_date"] = local_date
            elif changes["progress"] < 100:
                changes["completion_date"] = None
        result = db.execute(
            update(ProjectStep)
            .where(
                ProjectStep.id == step.id,
                ProjectStep.project_id == step.project_id,
                ProjectStep.lock_version == row.lock_version,
                ProjectStep.progress < 100,
                ProjectStep.planned_date <= local_date,
            )
            .values(**changes, lock_version=ProjectStep.lock_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ReviewVersionConflictError(
                "One or more Review Project Step versions are stale"
            )

    metadata = db.get(WorkspaceTrackingMetadata, workspace_id)
    if metadata is None:
        metadata = WorkspaceTrackingMetadata(workspace_id=workspace_id)
        db.add(metadata)
    metadata.last_review_saved_at = timestamp
    db.flush()
    return timestamp
