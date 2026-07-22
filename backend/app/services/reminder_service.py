import uuid

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_form import DailyFormDefinition, DailyFormSubmission
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.reminder import ReminderEvaluationResponse, ReminderItem, ReminderType
from app.services.workspace import get_workspace_membership


class ReminderPermissionError(PermissionError):
    pass


class ReminderTimezoneError(ValueError):
    pass


def _workspace_zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ReminderTimezoneError("Workspace timezone is invalid") from error


def _form_reminder(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    local_date: date,
    local_evaluated_at: datetime,
    zone: ZoneInfo,
) -> ReminderItem | None:
    definition = db.scalar(select(DailyFormDefinition).where(DailyFormDefinition.workspace_id == workspace_id))
    if definition is None:
        return None
    threshold_local = datetime.combine(local_date, time(9), tzinfo=zone)
    if local_evaluated_at < threshold_local:
        return None
    submission = db.scalar(select(DailyFormSubmission.id).where(
        DailyFormSubmission.workspace_id == workspace_id,
        DailyFormSubmission.user_id == user_id,
        DailyFormSubmission.submission_date == local_date,
        DailyFormSubmission.definition_id == definition.id,
    ))
    if submission is not None:
        return None
    return ReminderItem(
        reminder_type=ReminderType.DAILY_FORM_REQUIRED,
        entity_id=definition.id,
        title="Complete daily form",
        scheduled_for=threshold_local.astimezone(timezone.utc),
        local_date=local_date,
        metadata={"definition_id": str(definition.id), "submission_date": local_date.isoformat()},
    )


def evaluate_reminders(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    evaluated_at: datetime,
) -> ReminderEvaluationResponse:
    if get_workspace_membership(db, workspace_id=workspace_id, user_id=current_user.id) is None:
        raise ReminderPermissionError("Workspace access denied")
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    zone = _workspace_zone(workspace.timezone)
    evaluated_utc = evaluated_at.astimezone(timezone.utc)
    local_evaluated_at = evaluated_utc.astimezone(zone)
    local_date = local_evaluated_at.date()

    reminders: list[ReminderItem] = []
    form = _form_reminder(
        db, workspace_id=workspace_id, user_id=current_user.id, local_date=local_date,
        local_evaluated_at=local_evaluated_at, zone=zone,
    )
    if form is not None:
        reminders.append(form)

    window_end = evaluated_utc + timedelta(minutes=60)
    tasks = db.scalars(select(Task).where(
        Task.workspace_id == workspace_id,
        Task.created_by_id == current_user.id,
        Task.outcome.is_(None),
        Task.scheduled_at.is_not(None),
        Task.scheduled_at <= window_end,
    )).all()
    for task in tasks:
        scheduled = task.scheduled_at.astimezone(timezone.utc)
        if scheduled <= evaluated_utc:
            reminder_type = ReminderType.TASK_OVERDUE
            minutes_key = "minutes_overdue"
            minutes = int((evaluated_utc - scheduled).total_seconds() // 60)
        else:
            reminder_type = ReminderType.TASK_DUE
            minutes_key = "minutes_until_due"
            minutes = int((scheduled - evaluated_utc).total_seconds() // 60)
        metadata: dict[str, str | int | float | bool | None] = {
            "task_id": str(task.id),
            minutes_key: max(0, minutes),
        }
        if task.task_series_id is not None:
            metadata["task_series_id"] = str(task.task_series_id)
        reminders.append(ReminderItem(
            reminder_type=reminder_type,
            entity_id=task.id,
            title=task.title,
            scheduled_for=scheduled,
            local_date=scheduled.astimezone(zone).date(),
            metadata=metadata,
        ))

    rank = {ReminderType.DAILY_FORM_REQUIRED: 0, ReminderType.TASK_OVERDUE: 1, ReminderType.TASK_DUE: 2}
    reminders.sort(key=lambda item: (rank[item.reminder_type], item.scheduled_for, item.entity_id))
    return ReminderEvaluationResponse(
        workspace_id=workspace_id,
        user_id=current_user.id,
        evaluated_at=evaluated_at,
        local_date=local_date,
        timezone=zone.key,
        reminder_count=len(reminders),
        reminders=reminders,
    )
