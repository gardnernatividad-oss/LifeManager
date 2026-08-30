import uuid

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import MasterTask, PendingItem, Project, ProjectStage, Task, Workspace, WorkspaceMember
from app.models.enums import MembershipStatus, WorkspaceLifecycle
from app.services.v2_calendar import CalendarActivityProjection, list_my_calendar


UPCOMING_ACTIVITY_LIMIT = 5
UPCOMING_DAY_HORIZON = 7
ATTENTION_LIMIT = 20


@dataclass(frozen=True)
class HomeAttentionProjection:
    type: str
    id: uuid.UUID
    workspace: Workspace
    name: str
    planned_date: date
    project_id: uuid.UUID | None = None


@dataclass(frozen=True)
class HomeSummaryProjection:
    local_date: date
    today: tuple[int, int, int, int]
    upcoming_activities: list[CalendarActivityProjection]
    attention: list[HomeAttentionProjection]
    upcoming_days: list[tuple[date, int, int, int, int]]


def _scope(user_id: uuid.UUID):
    return (
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == MembershipStatus.ACTIVE,
        Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
    )


def _daily_counts(db: Session, *, user_id: uuid.UUID, date_from: date, date_until: date):
    scope = _scope(user_id)
    statements = (
        select(Task.planned_date, func.count(Task.id)).join(Workspace, Workspace.id == Task.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == Task.workspace_id, WorkspaceMember.user_id == user_id)).where(Task.responsible_user_id == user_id, Task.result.is_(None), Task.planned_date.between(date_from, date_until), *scope).group_by(Task.planned_date),
        select(PendingItem.planned_date, func.count(PendingItem.id)).join(Workspace, Workspace.id == PendingItem.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == PendingItem.workspace_id, WorkspaceMember.user_id == user_id)).where(PendingItem.responsible_user_id == user_id, PendingItem.is_active.is_(True), PendingItem.progress < 100, PendingItem.planned_date.between(date_from, date_until), *scope).group_by(PendingItem.planned_date),
        select(ProjectStage.planned_date, func.count(ProjectStage.id)).join(Project, and_(Project.id == ProjectStage.project_id, Project.workspace_id == ProjectStage.workspace_id)).join(Workspace, Workspace.id == ProjectStage.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == ProjectStage.workspace_id, WorkspaceMember.user_id == user_id)).where(ProjectStage.responsible_user_id == user_id, ProjectStage.progress < 100, Project.is_active.is_(True), ProjectStage.planned_date.between(date_from, date_until), *scope).group_by(ProjectStage.planned_date),
    )
    counts: dict[date, list[int]] = {date_from + timedelta(days=offset): [0, 0, 0] for offset in range((date_until - date_from).days + 1)}
    for index, statement in enumerate(statements):
        for day, total in db.execute(statement).all():
            counts[day][index] = total
    return counts


def _attention(db: Session, *, user_id: uuid.UUID, today: date) -> list[HomeAttentionProjection]:
    scope = _scope(user_id)
    tasks = db.execute(select(Task, Workspace, MasterTask).join(Workspace, Workspace.id == Task.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == Task.workspace_id, WorkspaceMember.user_id == user_id)).outerjoin(MasterTask, and_(MasterTask.id == Task.master_task_id, MasterTask.workspace_id == Task.workspace_id)).where(Task.responsible_user_id == user_id, Task.result.is_(None), Task.planned_date < today, *scope).order_by(Task.planned_date, Task.id).limit(ATTENTION_LIMIT)).all()
    pending = db.execute(select(PendingItem, Workspace).join(Workspace, Workspace.id == PendingItem.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == PendingItem.workspace_id, WorkspaceMember.user_id == user_id)).where(PendingItem.responsible_user_id == user_id, PendingItem.is_active.is_(True), PendingItem.progress < 100, PendingItem.planned_date < today, *scope).order_by(PendingItem.planned_date, PendingItem.id).limit(ATTENTION_LIMIT)).all()
    stages = db.execute(select(ProjectStage, Project, Workspace).join(Project, and_(Project.id == ProjectStage.project_id, Project.workspace_id == ProjectStage.workspace_id)).join(Workspace, Workspace.id == ProjectStage.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == ProjectStage.workspace_id, WorkspaceMember.user_id == user_id)).where(ProjectStage.responsible_user_id == user_id, ProjectStage.progress < 100, Project.is_active.is_(True), ProjectStage.planned_date < today, *scope).order_by(ProjectStage.planned_date, ProjectStage.id).limit(ATTENTION_LIMIT)).all()
    items = [HomeAttentionProjection("TASK", item.id, workspace, item.custom_name or master.name, item.planned_date) for item, workspace, master in tasks]
    items += [HomeAttentionProjection("PENDING_ITEM", item.id, workspace, item.name, item.planned_date) for item, workspace in pending]
    items += [HomeAttentionProjection("PROJECT_STAGE", item.id, workspace, f"{project.name} · {item.name}", item.planned_date, project.id) for item, project, workspace in stages]
    return sorted(items, key=lambda item: (item.planned_date, item.type, str(item.id)))[:ATTENTION_LIMIT]


def get_home_summary(db: Session, *, user_id: uuid.UUID, timezone_name: str, now: datetime) -> HomeSummaryProjection:
    zone = ZoneInfo(timezone_name)
    today = now.astimezone(zone).date()
    date_until = today + timedelta(days=UPCOMING_DAY_HORIZON)
    range_start = datetime.combine(today, datetime.min.time(), zone)
    range_end = datetime.combine(date_until + timedelta(days=1), datetime.min.time(), zone)
    daily_activities = list_my_calendar(
        db, user_id=user_id, range_start=range_start, range_end=range_end, now=now,
        require_active_access=True,
    )
    upcoming = list_my_calendar(
        db, user_id=user_id, range_start=now, range_end=datetime.max.replace(tzinfo=timezone.utc), now=now,
        require_active_access=True, future_only=True, limit=UPCOMING_ACTIVITY_LIMIT,
    )
    counts = _daily_counts(db, user_id=user_id, date_from=today, date_until=date_until)
    activity_counts = {day: 0 for day in counts}
    for projection in daily_activities:
        first = max(today, projection.activity.starts_at.astimezone(zone).date())
        last = min(date_until, (projection.activity.ends_at.astimezone(zone) - timedelta(microseconds=1)).date())
        for offset in range(max(0, (last - first).days) + 1):
            activity_counts[first + timedelta(days=offset)] += 1
    upcoming_days = [(day, *counts[day], activity_counts[day]) for day in sorted(counts) if day > today]
    return HomeSummaryProjection(today, (*counts[today], activity_counts[today]), upcoming, _attention(db, user_id=user_id, today=today), upcoming_days)
