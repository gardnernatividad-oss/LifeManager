import uuid

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_form import DailyFormDefinition, DailyFormSubmission
from app.models.task import Task
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.workspace import Workspace
from app.models.workspace_settings import WorkspaceSettings
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
    reminder_time: time,
) -> ReminderItem | None:
    definition = db.scalar(select(DailyFormDefinition).where(DailyFormDefinition.workspace_id == workspace_id))
    if definition is None:
        return None
    threshold_local = datetime.combine(local_date, reminder_time, tzinfo=zone)
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
    workspace_settings = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )
    user_settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    workspace_timezone = (
        workspace_settings.timezone
        if workspace_settings is not None
        else workspace.timezone
    )
    zone = _workspace_zone(workspace_timezone)
    evaluated_utc = evaluated_at.astimezone(timezone.utc)
    local_evaluated_at = evaluated_utc.astimezone(zone)
    local_date = local_evaluated_at.date()

    reminders: list[ReminderItem] = []
    form_enabled = (
        (workspace_settings.daily_form_enabled if workspace_settings is not None else True)
        and (user_settings.daily_form_reminders_enabled if user_settings is not None else True)
    )
    if form_enabled:
        reminder_time = (
            user_settings.daily_form_reminder_time
            if user_settings is not None
            else workspace_settings.daily_form_reminder_time
            if workspace_settings is not None
            else time(9)
        )
        form = _form_reminder(
            db, workspace_id=workspace_id, user_id=current_user.id, local_date=local_date,
            local_evaluated_at=local_evaluated_at, zone=zone, reminder_time=reminder_time,
        )
        if form is not None:
            reminders.append(form)

    due_enabled = user_settings.task_due_reminders_enabled if user_settings is not None else True
    overdue_enabled = user_settings.task_overdue_reminders_enabled if user_settings is not None else True
    due_minutes = user_settings.task_due_reminder_minutes if user_settings is not None else 60
    due_possible = due_enabled and due_minutes > 0
    tasks = []
    if due_possible or overdue_enabled:
        task_filters: list[object] = [
            Task.workspace_id == workspace_id,
            Task.created_by_id == current_user.id,
            Task.outcome.is_(None),
            Task.scheduled_at.is_not(None),
        ]
        if due_possible and overdue_enabled:
            task_filters.append(Task.scheduled_at <= evaluated_utc + timedelta(minutes=due_minutes))
        elif due_possible:
            task_filters.extend((
                Task.scheduled_at > evaluated_utc,
                Task.scheduled_at <= evaluated_utc + timedelta(minutes=due_minutes),
            ))
        else:
            task_filters.append(Task.scheduled_at <= evaluated_utc)
        tasks = db.scalars(select(Task).where(*task_filters)).all()
    for task in tasks:
        scheduled = task.scheduled_at.astimezone(timezone.utc)
        if scheduled <= evaluated_utc:
            if not overdue_enabled:
                continue
            reminder_type = ReminderType.TASK_OVERDUE
            minutes_key = "minutes_overdue"
            minutes = int((evaluated_utc - scheduled).total_seconds() // 60)
        else:
            if not due_possible:
                continue
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
