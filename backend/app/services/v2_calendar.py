import uuid

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Date, and_, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    Activity, ActivityMaster, ActivityParticipant, Category, MasterTask, PendingItem,
    Project, ProjectStage, Task, User, Workspace, WorkspaceMember,
)
from app.models.enums import ActivityStatus, MembershipStatus, ParticipantCalendarStatus, WorkspaceKind, WorkspaceLifecycle
from app.services.v2_activity import ActivityTemporalState, temporal_state


@dataclass(frozen=True)
class CalendarActivityProjection:
    activity: Activity
    workspace: Workspace
    master: ActivityMaster | None
    category: Category
    organizer: User
    participants: list[User]
    temporal_state: ActivityTemporalState
    can_edit: bool
    can_delete: bool
    can_leave_participation: bool


@dataclass(frozen=True)
class CalendarUntimedProjection:
    id: uuid.UUID
    workspace: Workspace
    name: str
    planned_date: date


@dataclass(frozen=True)
class CalendarDayCountProjection:
    date: date
    activities: int = 0
    tasks: int = 0
    pending_items: int = 0
    project_stages: int = 0


def list_my_calendar(
    db: Session, *, user_id: uuid.UUID, range_start: datetime, range_end: datetime, now: datetime,
    workspace_id: uuid.UUID | None = None, require_active_access: bool = False,
    future_only: bool = False, limit: int | None = None,
) -> list[CalendarActivityProjection]:
    own_participation = aliased(ActivityParticipant)
    current_membership = aliased(WorkspaceMember)
    visibility = (
        and_(
            own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
            current_membership.status == MembershipStatus.ACTIVE,
        )
        if require_active_access
        else or_(
            and_(Activity.starts_at > now, own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE, Workspace.lifecycle == WorkspaceLifecycle.ACTIVE, current_membership.status == MembershipStatus.ACTIVE),
            and_(Activity.starts_at <= now, or_(own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE, own_participation.removed_at >= Activity.starts_at)),
        )
    )
    statement = (
        select(Activity, Workspace, ActivityMaster, Category, User, current_membership)
        .join(own_participation, and_(own_participation.activity_id == Activity.id, own_participation.workspace_id == Activity.workspace_id))
        .join(Workspace, Workspace.id == Activity.workspace_id)
        .outerjoin(ActivityMaster, and_(ActivityMaster.id == Activity.activity_master_id, ActivityMaster.workspace_id == Activity.workspace_id))
        .join(Category, and_(Category.workspace_id == Activity.workspace_id, or_(
            Category.id == ActivityMaster.category_id,
            Category.id == Activity.custom_category_id,
        )))
        .join(User, User.id == Activity.organizer_user_id)
        .outerjoin(current_membership, and_(current_membership.workspace_id == Activity.workspace_id, current_membership.user_id == user_id))
        .where(
            own_participation.user_id == user_id,
            Activity.status == ActivityStatus.SCHEDULED,
            Activity.starts_at < range_end,
            Activity.ends_at > range_start,
            visibility,
        )
        .order_by(Activity.starts_at, Activity.ends_at, Activity.id)
    )
    if workspace_id is not None:
        statement = statement.where(Activity.workspace_id == workspace_id)
    if future_only:
        statement = statement.where(Activity.starts_at > now)
    if limit is not None:
        statement = statement.limit(limit)
    rows = db.execute(statement).all()
    if not rows:
        return []
    activity_ids = [activity.id for activity, *_ in rows]
    participant_rows = db.execute(
        select(ActivityParticipant, User, Activity.starts_at)
        .join(User, User.id == ActivityParticipant.user_id)
        .join(Activity, and_(Activity.id == ActivityParticipant.activity_id, Activity.workspace_id == ActivityParticipant.workspace_id))
        .where(ActivityParticipant.activity_id.in_(activity_ids))
        .order_by(ActivityParticipant.activity_id, User.first_name, User.last_name, User.id)
    ).all()
    participants: dict[uuid.UUID, list[User]] = {activity_id: [] for activity_id in activity_ids}
    for participant, user, starts_at in participant_rows:
        if participant.calendar_status == ParticipantCalendarStatus.VISIBLE or (participant.removed_at is not None and participant.removed_at >= starts_at):
            participants[participant.activity_id].append(user)
    result: list[CalendarActivityProjection] = []
    for activity, workspace, master, category, organizer, membership in rows:
        state = temporal_state(activity, now=now)
        active_access = workspace.lifecycle == WorkspaceLifecycle.ACTIVE and membership is not None and membership.status == MembershipStatus.ACTIVE
        mutable = active_access and state == "FUTURE" and activity.status == ActivityStatus.SCHEDULED and activity.generation_batch_id is None
        own_visible = any(user.id == user_id for user in participants[activity.id])
        result.append(CalendarActivityProjection(
            activity=activity, workspace=workspace, master=master, category=category, organizer=organizer,
            participants=participants[activity.id], temporal_state=state,
            can_edit=mutable, can_delete=mutable,
            can_leave_participation=mutable and workspace.kind == WorkspaceKind.SHARED and own_visible,
        ))
    return result


def _accessible_scope(user_id: uuid.UUID, workspace_id: uuid.UUID | None):
    conditions = [
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == MembershipStatus.ACTIVE,
        Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
    ]
    if workspace_id is not None:
        conditions.append(Workspace.id == workspace_id)
    return conditions


def list_calendar_untimed(
    db: Session, *, user_id: uuid.UUID, date_from: date, date_until: date,
    workspace_id: uuid.UUID | None = None,
) -> tuple[list[CalendarUntimedProjection], list[CalendarUntimedProjection], list[CalendarUntimedProjection]]:
    scope = _accessible_scope(user_id, workspace_id)
    tasks = db.execute(
        select(Task, Workspace, MasterTask)
        .join(Workspace, Workspace.id == Task.workspace_id)
        .join(WorkspaceMember, and_(WorkspaceMember.workspace_id == Task.workspace_id, WorkspaceMember.user_id == user_id))
        .outerjoin(MasterTask, and_(MasterTask.id == Task.master_task_id, MasterTask.workspace_id == Task.workspace_id))
        .where(Task.responsible_user_id == user_id, Task.planned_date.between(date_from, date_until), *scope)
        .order_by(Task.planned_date, Task.id)
    ).all()
    pending = db.execute(
        select(PendingItem, Workspace)
        .join(Workspace, Workspace.id == PendingItem.workspace_id)
        .join(WorkspaceMember, and_(WorkspaceMember.workspace_id == PendingItem.workspace_id, WorkspaceMember.user_id == user_id))
        .where(PendingItem.responsible_user_id == user_id, PendingItem.planned_date.between(date_from, date_until), *scope)
        .order_by(PendingItem.planned_date, PendingItem.id)
    ).all()
    stages = db.execute(
        select(ProjectStage, Project, Workspace)
        .join(Project, and_(Project.id == ProjectStage.project_id, Project.workspace_id == ProjectStage.workspace_id))
        .join(Workspace, Workspace.id == ProjectStage.workspace_id)
        .join(WorkspaceMember, and_(WorkspaceMember.workspace_id == ProjectStage.workspace_id, WorkspaceMember.user_id == user_id))
        .where(ProjectStage.responsible_user_id == user_id, ProjectStage.planned_date.between(date_from, date_until), *scope)
        .order_by(ProjectStage.planned_date, ProjectStage.id)
    ).all()
    return (
        [CalendarUntimedProjection(item.id, workspace, item.custom_name or master.name, item.planned_date) for item, workspace, master in tasks],
        [CalendarUntimedProjection(item.id, workspace, item.name, item.planned_date) for item, workspace in pending],
        [CalendarUntimedProjection(item.id, workspace, f"{project.name} · {item.name}", item.planned_date) for item, project, workspace in stages],
    )


def calendar_daily_counts(
    db: Session, *, user_id: uuid.UUID, date_from: date, date_until: date,
    range_start: datetime, range_end: datetime, now: datetime, timezone_name: str,
    workspace_id: uuid.UUID | None = None,
) -> list[CalendarDayCountProjection]:
    counts: dict[date, list[int]] = {}
    own_participation = aliased(ActivityParticipant)
    current_membership = aliased(WorkspaceMember)
    activity_day = cast(func.timezone(timezone_name, Activity.starts_at), Date)
    activity_statement = (
        select(activity_day.label("day"), func.count(Activity.id))
        .join(own_participation, and_(own_participation.activity_id == Activity.id, own_participation.workspace_id == Activity.workspace_id))
        .join(Workspace, Workspace.id == Activity.workspace_id)
        .outerjoin(current_membership, and_(current_membership.workspace_id == Activity.workspace_id, current_membership.user_id == user_id))
        .where(
            own_participation.user_id == user_id, Activity.status == ActivityStatus.SCHEDULED,
            Activity.starts_at < range_end, Activity.ends_at > range_start,
            or_(
                and_(Activity.starts_at > now, own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE, Workspace.lifecycle == WorkspaceLifecycle.ACTIVE, current_membership.status == MembershipStatus.ACTIVE),
                and_(Activity.starts_at <= now, or_(own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE, own_participation.removed_at >= Activity.starts_at)),
            ),
        ).group_by(activity_day).order_by(activity_day)
    )
    if workspace_id is not None:
        activity_statement = activity_statement.where(Activity.workspace_id == workspace_id)
    for day, total in db.execute(activity_statement).all():
        counts.setdefault(day, [0, 0, 0, 0])[0] = total

    scope = _accessible_scope(user_id, workspace_id)
    statements = (
        select(Task.planned_date, func.count(Task.id)).join(Workspace, Workspace.id == Task.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == Task.workspace_id, WorkspaceMember.user_id == user_id)).where(Task.responsible_user_id == user_id, Task.planned_date.between(date_from, date_until), *scope).group_by(Task.planned_date),
        select(PendingItem.planned_date, func.count(PendingItem.id)).join(Workspace, Workspace.id == PendingItem.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == PendingItem.workspace_id, WorkspaceMember.user_id == user_id)).where(PendingItem.responsible_user_id == user_id, PendingItem.planned_date.between(date_from, date_until), *scope).group_by(PendingItem.planned_date),
        select(ProjectStage.planned_date, func.count(ProjectStage.id)).join(Project, and_(Project.id == ProjectStage.project_id, Project.workspace_id == ProjectStage.workspace_id)).join(Workspace, Workspace.id == ProjectStage.workspace_id).join(WorkspaceMember, and_(WorkspaceMember.workspace_id == ProjectStage.workspace_id, WorkspaceMember.user_id == user_id)).where(ProjectStage.responsible_user_id == user_id, ProjectStage.planned_date.between(date_from, date_until), *scope).group_by(ProjectStage.planned_date),
    )
    for index, statement in enumerate(statements, start=1):
        for day, total in db.execute(statement).all():
            counts.setdefault(day, [0, 0, 0, 0])[index] = total
    return [CalendarDayCountProjection(day, *values) for day, values in sorted(counts.items())]
