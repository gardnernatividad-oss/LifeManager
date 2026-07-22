import uuid

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskOutcome
from app.models.user import User
from app.services.workspace import get_workspace_membership


class TaskNotFound(LookupError):
    pass


class TaskPermission(PermissionError):
    pass


class TaskAlreadyResolved(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
    outcome: TaskOutcome,
) -> Task:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise TaskPermission("Workspace access denied")

    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.workspace_id == workspace_id,
        )
    )
    if task is None:
        raise TaskNotFound("Task not found")
    if task.outcome is not None:
        raise TaskAlreadyResolved("Task is already resolved")

    task.outcome = outcome
    task.resolved_at = _utc_now()
    db.flush()
    return task


def complete_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> Task:
    return _resolve_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
        outcome=TaskOutcome.COMPLETED,
    )


def mark_task_not_completed(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> Task:
    return _resolve_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
        outcome=TaskOutcome.NOT_COMPLETED,
    )


def cancel_task(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User,
) -> Task:
    return _resolve_task(
        db,
        workspace_id=workspace_id,
        task_id=task_id,
        current_user=current_user,
        outcome=TaskOutcome.CANCELLED,
    )
