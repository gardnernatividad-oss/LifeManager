import uuid

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Activity, ActivityMaster, ActivityParticipant, Category, User, Workspace, WorkspaceMember
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


def list_my_calendar(
    db: Session, *, user_id: uuid.UUID, range_start: datetime, range_end: datetime, now: datetime,
) -> list[CalendarActivityProjection]:
    own_participation = aliased(ActivityParticipant)
    current_membership = aliased(WorkspaceMember)
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
            or_(
                and_(
                    Activity.starts_at > now,
                    own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE,
                    Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
                    current_membership.status == MembershipStatus.ACTIVE,
                ),
                and_(
                    Activity.starts_at <= now,
                    or_(
                        own_participation.calendar_status == ParticipantCalendarStatus.VISIBLE,
                        own_participation.removed_at >= Activity.starts_at,
                    ),
                ),
            ),
        )
        .order_by(Activity.starts_at, Activity.ends_at, Activity.id)
    )
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
