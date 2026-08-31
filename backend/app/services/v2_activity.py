import uuid

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.activity_recurrence import InvalidLocalActivityTimeError, local_activity_datetime
from app.core.names import normalize_name
from app.core.recurrence import recurrence_dates
from app.models import Activity, ActivityMaster, ActivityParticipant, ActivityReminder, Category, GenerationBatch, User, WorkspaceMember
from app.models.enums import AccountStatus, ActivityStatus, GenerationEntityType, MembershipStatus, ParticipantCalendarStatus, WorkspaceKind
from app.schemas.v2_activity import ActivityCreate, ActivityMutationScope, ActivityTemporalState, ActivityUpdate, RecurringActivityCreate
from app.services.v2_workspace import WorkspaceAccess


class ActivityNotFoundError(LookupError):
    pass


class ActivityConflictError(ValueError):
    pass


class ActivityReferenceUnavailableError(ValueError):
    pass


class ActivityRecurrenceError(ValueError):
    pass


MAX_RECURRING_ACTIVITY_OCCURRENCES = 1000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint in {
            "fk_activities_organizer_membership", "fk_activities_master_workspace",
            "fk_activity_participants_activity_workspace", "fk_activity_participants_user_membership",
            "uq_activity_participants_activity_user",
        }:
            raise ActivityReferenceUnavailableError("Activity reference unavailable") from error
        if constraint in {"uq_activities_catalog_occurrence", "uq_activities_custom_occurrence", "uq_activities_batch_starts"}:
            raise ActivityConflictError("Activity occurrence already exists") from error
        raise


def _master(db: Session, *, workspace_id: uuid.UUID, master_id: uuid.UUID, assignable: bool) -> ActivityMaster:
    statement = select(ActivityMaster).where(ActivityMaster.id == master_id, ActivityMaster.workspace_id == workspace_id)
    if assignable:
        statement = statement.with_for_update()
    master = db.scalar(statement)
    if master is None or (assignable and not master.is_active):
        raise ActivityReferenceUnavailableError("Activity master unavailable")
    return master


def _category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, assignable: bool) -> Category:
    statement = select(Category).where(Category.id == category_id, Category.workspace_id == workspace_id)
    if assignable:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None or (assignable and not category.is_active):
        raise ActivityReferenceUnavailableError("Activity Category unavailable")
    return category


def _source_values(db: Session, *, workspace_id: uuid.UUID, source):
    if source.activity_master_id is not None:
        master = _master(db, workspace_id=workspace_id, master_id=source.activity_master_id, assignable=True)
        return master.id, master.name, None
    title, _ = normalize_name(source.custom_name, max_length=255, field_label="Activity")
    category = _category(db, workspace_id=workspace_id, category_id=source.custom_category_id, assignable=True)
    return None, title, category.id


def _eligible_users(db: Session, *, workspace_id: uuid.UUID, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            User.id.in_(user_ids), User.account_status == AccountStatus.ACTIVE,
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .order_by(User.id)
        .with_for_update()
    ).all()
    users = {user.id: user for user, _ in rows}
    if set(users) != user_ids:
        raise ActivityReferenceUnavailableError("Activity user unavailable")
    return users


def _activity(db: Session, *, workspace_id: uuid.UUID, activity_id: uuid.UUID, lock: bool = False) -> Activity:
    statement = select(Activity).options(selectinload(Activity.participants), selectinload(Activity.reminders)).where(Activity.id == activity_id, Activity.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    activity = db.scalar(statement)
    if activity is None:
        raise ActivityNotFoundError("Activity not found")
    return activity


def _require_future(activity: Activity, *, now: datetime) -> None:
    # Deliberately evaluated after SELECT FOR UPDATE: starts_at is the historical boundary.
    if activity.status != ActivityStatus.SCHEDULED or now >= activity.starts_at:
        raise ActivityConflictError("Activity is immutable")


def _check_version(activity: Activity, expected: int) -> None:
    if activity.lock_version != expected:
        raise ActivityConflictError("Activity version conflict")


def create_activity(db: Session, *, access: WorkspaceAccess, actor: User, activity_in: ActivityCreate) -> Activity:
    master_id, title, custom_category_id = _source_values(db, workspace_id=access.workspace.id, source=activity_in)
    if activity_in.starts_at <= _now():
        raise ActivityConflictError("Activity must start in the future")
    organizer_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (activity_in.organizer_user_id or actor.id)
    participant_ids = {access.workspace.owner_user_id} if access.workspace.kind == WorkspaceKind.PERSONAL else set(activity_in.participant_user_ids)
    _eligible_users(db, workspace_id=access.workspace.id, user_ids=participant_ids | {organizer_id})
    activity = Activity(
        workspace_id=access.workspace.id, organizer_user_id=organizer_id,
        activity_master_id=master_id, title=title, custom_category_id=custom_category_id,
        starts_at=activity_in.starts_at, ends_at=activity_in.ends_at,
        status=ActivityStatus.SCHEDULED, generation_batch_id=None,
    )
    db.add(activity)
    _flush(db)
    db.add_all(ActivityParticipant(activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user_id) for user_id in sorted(participant_ids, key=str))
    if activity_in.reminder_minutes_before is not None:
        db.add_all(ActivityReminder(activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user_id, minutes_before=activity_in.reminder_minutes_before) for user_id in sorted(participant_ids | {organizer_id}, key=str))
    _flush(db)
    return activity


def create_recurring_activities(
    db: Session, *, access: WorkspaceAccess, actor: User, activity_in: RecurringActivityCreate,
) -> list[Activity]:
    master_id, title, custom_category_id = _source_values(db, workspace_id=access.workspace.id, source=activity_in)
    organizer_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (activity_in.organizer_user_id or actor.id)
    participant_ids = {access.workspace.owner_user_id} if access.workspace.kind == WorkspaceKind.PERSONAL else set(activity_in.participant_user_ids)
    _eligible_users(db, workspace_id=access.workspace.id, user_ids=participant_ids | {organizer_id})
    recurrence = activity_in.recurrence
    dates = recurrence_dates(pattern=recurrence.pattern, date_from=recurrence.date_from,
                             date_until=recurrence.date_until, weekdays=recurrence.weekdays,
                             month_days=recurrence.month_days)
    if not dates:
        raise ActivityRecurrenceError("Recurrence must generate at least one occurrence")
    if len(dates) > MAX_RECURRING_ACTIVITY_OCCURRENCES:
        raise ActivityRecurrenceError("Recurrence exceeds occurrence limit")
    try:
        instants = [(
            local_activity_datetime(local_date=value, local_time=activity_in.start_time, timezone_name=activity_in.timezone),
            local_activity_datetime(local_date=value, local_time=activity_in.end_time, timezone_name=activity_in.timezone),
        ) for value in dates]
    except InvalidLocalActivityTimeError as error:
        raise ActivityRecurrenceError(str(error)) from error
    current = _now()
    if any(starts_at <= current or ends_at <= starts_at for starts_at, ends_at in instants):
        raise ActivityRecurrenceError("Every Activity occurrence must be future and have a valid range")
    starts = [starts_at for starts_at, _ in instants]
    collision = db.scalar(select(Activity.id).where(
        Activity.workspace_id == access.workspace.id,
        Activity.activity_master_id == master_id,
        Activity.custom_category_id == custom_category_id,
        Activity.title == title,
        Activity.organizer_user_id == organizer_id,
        Activity.starts_at.in_(starts),
    ).limit(1))
    if collision is not None:
        raise ActivityConflictError("Activity occurrence already exists")
    batch = GenerationBatch(
        workspace_id=access.workspace.id, entity_type=GenerationEntityType.ACTIVITY,
        pattern=recurrence.pattern, date_from=recurrence.date_from, date_until=recurrence.date_until,
        weekdays=recurrence.weekdays, month_days=recurrence.month_days,
        timezone=activity_in.timezone, created_by_user_id=actor.id,
    )
    db.add(batch)
    _flush(db)
    activities = [Activity(
        workspace_id=access.workspace.id, organizer_user_id=organizer_id,
        activity_master_id=master_id, title=title, custom_category_id=custom_category_id,
        starts_at=starts_at, ends_at=ends_at, status=ActivityStatus.SCHEDULED,
        generation_batch_id=batch.id,
    ) for starts_at, ends_at in instants]
    db.add_all(activities)
    _flush(db)
    db.add_all(ActivityParticipant(activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user_id)
               for activity in activities for user_id in sorted(participant_ids, key=str))
    if activity_in.reminder_minutes_before is not None:
        db.add_all(ActivityReminder(activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user_id, minutes_before=activity_in.reminder_minutes_before)
                   for activity in activities for user_id in sorted(participant_ids | {organizer_id}, key=str))
    _flush(db)
    return activities


def list_activities(
    db: Session, *, workspace_id: uuid.UUID, page: int, page_size: int,
    starts_from: datetime | None = None, starts_until: datetime | None = None,
    activity_master_id: uuid.UUID | None = None, category_id: uuid.UUID | None = None,
    organizer_user_id: uuid.UUID | None = None, participant_user_id: uuid.UUID | None = None,
    custom: bool | None = None,
) -> tuple[list[Activity], int]:
    filters = [Activity.workspace_id == workspace_id]
    if starts_from is not None: filters.append(Activity.starts_at >= starts_from)
    if starts_until is not None: filters.append(Activity.starts_at <= starts_until)
    if activity_master_id is not None: filters.append(Activity.activity_master_id == activity_master_id)
    if category_id is not None: filters.append(or_(ActivityMaster.category_id == category_id, Activity.custom_category_id == category_id))
    if organizer_user_id is not None: filters.append(Activity.organizer_user_id == organizer_user_id)
    if participant_user_id is not None:
        filters.append(ActivityParticipant.user_id == participant_user_id)
        filters.append(ActivityParticipant.calendar_status == ParticipantCalendarStatus.VISIBLE)
    if custom is True: filters.append(Activity.activity_master_id.is_(None))
    elif custom is False: filters.append(Activity.activity_master_id.is_not(None))
    joins_master = category_id is not None
    joins_participant = participant_user_id is not None
    count = select(func.count(func.distinct(Activity.id))).select_from(Activity)
    items = select(Activity).options(selectinload(Activity.participants), selectinload(Activity.reminders))
    if joins_master:
        count = count.outerjoin(ActivityMaster, and_(ActivityMaster.id == Activity.activity_master_id, ActivityMaster.workspace_id == Activity.workspace_id))
        items = items.outerjoin(ActivityMaster, and_(ActivityMaster.id == Activity.activity_master_id, ActivityMaster.workspace_id == Activity.workspace_id))
    if joins_participant:
        count = count.join(ActivityParticipant, and_(ActivityParticipant.activity_id == Activity.id, ActivityParticipant.workspace_id == Activity.workspace_id))
        items = items.join(ActivityParticipant, and_(ActivityParticipant.activity_id == Activity.id, ActivityParticipant.workspace_id == Activity.workspace_id))
    total = db.scalar(count.where(*filters)) or 0
    result = list(db.scalars(items.where(*filters).order_by(Activity.starts_at, Activity.id).offset((page - 1) * page_size).limit(page_size)).unique().all())
    return result, int(total)


def get_activity(db: Session, *, workspace_id: uuid.UUID, activity_id: uuid.UUID) -> Activity:
    return _activity(db, workspace_id=workspace_id, activity_id=activity_id)


def _mutation_scope_activities(
    db: Session, *, workspace_id: uuid.UUID, activity_id: uuid.UUID,
    scope: ActivityMutationScope, now: datetime,
) -> tuple[Activity, list[Activity], GenerationBatch | None]:
    if scope == "THIS":
        activity = _activity(db, workspace_id=workspace_id, activity_id=activity_id, lock=True)
        _require_future(activity, now=now)
        return activity, [activity], None
    identified = _activity(db, workspace_id=workspace_id, activity_id=activity_id)
    if identified.generation_batch_id is None:
        raise ActivityConflictError("Standalone Activity does not support future scope")
    batch = db.scalar(select(GenerationBatch).where(
        GenerationBatch.id == identified.generation_batch_id,
        GenerationBatch.workspace_id == workspace_id,
        GenerationBatch.entity_type == GenerationEntityType.ACTIVITY,
    ).with_for_update())
    if batch is None:
        raise ActivityConflictError("Activity batch unavailable")
    activities = list(db.scalars(select(Activity).options(selectinload(Activity.participants)).where(
        Activity.workspace_id == workspace_id,
        Activity.generation_batch_id == batch.id,
    ).order_by(Activity.starts_at, Activity.id).with_for_update().execution_options(populate_existing=True)).unique().all())
    activity = next((item for item in activities if item.id == activity_id), None)
    if activity is None:
        raise ActivityConflictError("Activity changed during scope selection")
    _require_future(activity, now=now)
    affected = [item for item in activities if item.starts_at >= activity.starts_at and item.starts_at > now and item.status == ActivityStatus.SCHEDULED]
    if activity not in affected:
        raise ActivityConflictError("Activity cannot initiate future scope")
    return activity, affected, batch


def _set_participants(
    db: Session, *, activities: list[Activity], requested: set[uuid.UUID], changed_at: datetime,
) -> None:
    activity_ids = [item.id for item in activities]
    rows = list(db.scalars(select(ActivityParticipant).where(
        ActivityParticipant.activity_id.in_(activity_ids),
        ActivityParticipant.workspace_id == activities[0].workspace_id,
    ).order_by(ActivityParticipant.activity_id, ActivityParticipant.user_id).with_for_update()))
    by_activity = {(item.activity_id, item.user_id): item for item in rows}
    reminders = list(db.scalars(select(ActivityReminder).where(
        ActivityReminder.activity_id.in_(activity_ids),
        ActivityReminder.workspace_id == activities[0].workspace_id,
    ).order_by(ActivityReminder.activity_id, ActivityReminder.user_id).with_for_update()))
    reminder_by_key = {(item.activity_id, item.user_id): item for item in reminders}
    additions: list[ActivityParticipant] = []
    for activity in activities:
        current_users = {user_id for (activity_id, user_id) in by_activity if activity_id == activity.id}
        for user_id in current_users:
            item = by_activity[(activity.id, user_id)]
            desired = user_id in requested
            if desired and item.calendar_status != ParticipantCalendarStatus.VISIBLE:
                item.calendar_status, item.removed_at, item.lock_version = ParticipantCalendarStatus.VISIBLE, None, item.lock_version + 1
            elif not desired and item.calendar_status == ParticipantCalendarStatus.VISIBLE:
                item.calendar_status, item.removed_at, item.lock_version = ParticipantCalendarStatus.REMOVED, changed_at, item.lock_version + 1
                reminder = reminder_by_key.get((activity.id, user_id))
                if reminder is not None and reminder.is_enabled:
                    reminder.is_enabled = False; reminder.lock_version += 1
        additions.extend(ActivityParticipant(activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user_id) for user_id in sorted(requested - current_users, key=str))
    db.add_all(additions)


def update_activity(db: Session, *, access: WorkspaceAccess, activity_id: uuid.UUID, activity_in: ActivityUpdate) -> Activity:
    now = _now()
    activity, affected, batch = _mutation_scope_activities(db, workspace_id=access.workspace.id, activity_id=activity_id, scope=activity_in.scope, now=now)
    _check_version(activity, activity_in.lock_version)
    values = activity_in.model_dump(exclude_unset=True, exclude={"lock_version", "scope", "participant_user_ids", "reminder_minutes_before"})
    if access.workspace.kind == WorkspaceKind.PERSONAL:
        values.pop("organizer_user_id", None)
    starts_at = values.get("starts_at", activity.starts_at); ends_at = values.get("ends_at", activity.ends_at)
    if starts_at <= now or ends_at <= starts_at:
        raise ActivityConflictError("Invalid Activity time range")
    if activity_in.scope == "THIS_AND_FUTURE" and ("starts_at" in values or "ends_at" in values):
        if batch is None:
            raise ActivityConflictError("Activity batch unavailable")
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(batch.timezone)
        selected_date = activity.starts_at.astimezone(zone).date()
        if starts_at.astimezone(zone).date() != selected_date or ends_at.astimezone(zone).date() != selected_date:
            raise ActivityConflictError("Future scope cannot change occurrence dates")
        start_time, end_time = starts_at.astimezone(zone).time().replace(tzinfo=None), ends_at.astimezone(zone).time().replace(tzinfo=None)
        try:
            propagated = [(item, local_activity_datetime(local_date=item.starts_at.astimezone(zone).date(), local_time=start_time, timezone_name=batch.timezone), local_activity_datetime(local_date=item.starts_at.astimezone(zone).date(), local_time=end_time, timezone_name=batch.timezone)) for item in affected]
        except InvalidLocalActivityTimeError as error:
            raise ActivityConflictError("Invalid local Activity time") from error
        if any(new_start <= now or new_end <= new_start for _, new_start, new_end in propagated):
            raise ActivityConflictError("Invalid propagated Activity time")
        values.pop("starts_at", None); values.pop("ends_at", None)
    else:
        propagated = [(activity, starts_at, ends_at)] if ("starts_at" in values or "ends_at" in values) else []
    source_fields = {"activity_master_id", "custom_name", "custom_category_id"} & values.keys()
    if activity.activity_master_id is not None:
        if source_fields - {"activity_master_id"}:
            raise ActivityConflictError("Activity source cannot be converted")
        if "activity_master_id" in values and values["activity_master_id"] != activity.activity_master_id:
            master = _master(db, workspace_id=access.workspace.id, master_id=values["activity_master_id"], assignable=True)
            activity.activity_master_id, activity.title, activity.custom_category_id = master.id, master.name, None
    else:
        if "activity_master_id" in source_fields:
            raise ActivityConflictError("Activity source cannot be converted")
        if "custom_name" in values:
            activity.title, _ = normalize_name(values["custom_name"], max_length=255, field_label="Activity")
        if "custom_category_id" in values:
            activity.custom_category_id = _category(db, workspace_id=access.workspace.id, category_id=values["custom_category_id"], assignable=True).id
    if "organizer_user_id" in values:
        _eligible_users(db, workspace_id=access.workspace.id, user_ids={values["organizer_user_id"]})
    participant_ids = activity_in.participant_user_ids
    if access.workspace.kind == WorkspaceKind.PERSONAL and participant_ids is not None:
        participant_ids = [access.workspace.owner_user_id]
    if participant_ids is not None:
        requested = set(participant_ids)
        _eligible_users(db, workspace_id=access.workspace.id, user_ids=requested)
        _set_participants(db, activities=affected, requested=requested, changed_at=now)
    reminder_is_explicit = "reminder_minutes_before" in activity_in.model_fields_set
    if reminder_is_explicit or participant_ids is not None or "organizer_user_id" in values:
        minutes = activity_in.reminder_minutes_before if reminder_is_explicit else None
        activity_ids = [item.id for item in affected]
        reminders = list(db.scalars(select(ActivityReminder).where(ActivityReminder.activity_id.in_(activity_ids)).order_by(ActivityReminder.activity_id, ActivityReminder.user_id).with_for_update()))
        by_key = {(item.activity_id, item.user_id): item for item in reminders}
        for item in affected:
            organizer_id = values.get("organizer_user_id", item.organizer_user_id)
            visible_participants = requested if participant_ids is not None else {
                participant.user_id
                for participant in item.participants
                if participant.calendar_status == ParticipantCalendarStatus.VISIBLE
            }
            eligible = {organizer_id} | visible_participants
            inherited_minutes = next(
                (reminder.minutes_before for reminder in reminders if reminder.activity_id == item.id and reminder.is_enabled),
                None,
            )
            effective_minutes = minutes if reminder_is_explicit else inherited_minutes
            for reminder in reminders:
                if reminder.activity_id == item.id and reminder.user_id not in eligible and reminder.is_enabled:
                    reminder.is_enabled = False
                    reminder.lock_version += 1
            for user_id in eligible:
                reminder = by_key.get((item.id, user_id))
                if reminder_is_explicit and effective_minutes is None:
                    if reminder is not None and reminder.is_enabled: reminder.is_enabled = False; reminder.lock_version += 1
                elif effective_minutes is not None:
                    if reminder is None:
                        db.add(ActivityReminder(activity_id=item.id, workspace_id=item.workspace_id, user_id=user_id, minutes_before=effective_minutes))
                    else:
                        reminder.minutes_before = effective_minutes; reminder.is_enabled = True; reminder.lock_version += 1
    for item in affected:
        if source_fields:
            item.activity_master_id, item.title, item.custom_category_id = activity.activity_master_id, activity.title, activity.custom_category_id
        for field in ("organizer_user_id",):
            if field in values: setattr(item, field, values[field])
        item.lock_version += 1
    for item, new_start, new_end in propagated:
        item.starts_at, item.ends_at = new_start, new_end
    _flush(db)
    return activity


def delete_activity(db: Session, *, access: WorkspaceAccess, activity_id: uuid.UUID, expected_version: int, actor: User | None = None, scope: ActivityMutationScope = "THIS") -> None:
    now = _now(); activity, affected, _ = _mutation_scope_activities(db, workspace_id=access.workspace.id, activity_id=activity_id, scope=scope, now=now)
    _check_version(activity, expected_version)
    if access.workspace.kind == WorkspaceKind.PERSONAL:
        for item in affected: db.delete(item)
    else:
        cancelled_by_user_id = actor.id if actor is not None else access.membership.user_id
        for item in affected:
            item.status = ActivityStatus.CANCELLED; item.cancelled_at = now
            item.cancelled_by_user_id = cancelled_by_user_id; item.lock_version += 1
        reminders = list(db.scalars(select(ActivityReminder).where(
            ActivityReminder.workspace_id == access.workspace.id,
            ActivityReminder.activity_id.in_([item.id for item in affected]),
        ).order_by(ActivityReminder.activity_id, ActivityReminder.user_id).with_for_update()))
        for reminder in reminders:
            if reminder.is_enabled:
                reminder.is_enabled = False
                reminder.lock_version += 1
    _flush(db)


def leave_activity(db: Session, *, access: WorkspaceAccess, actor: User, activity_id: uuid.UUID, expected_version: int, scope: ActivityMutationScope = "THIS") -> Activity:
    now = _now(); activity, affected, _ = _mutation_scope_activities(db, workspace_id=access.workspace.id, activity_id=activity_id, scope=scope, now=now)
    _check_version(activity, expected_version)
    participants = list(db.scalars(select(ActivityParticipant).where(
        ActivityParticipant.activity_id.in_([item.id for item in affected]), ActivityParticipant.user_id == actor.id,
    ).order_by(ActivityParticipant.activity_id).with_for_update()))
    if not any(item.activity_id == activity.id and item.calendar_status == ParticipantCalendarStatus.VISIBLE for item in participants):
        raise ActivityConflictError("Active participation not found")
    for participant in participants:
        if participant.calendar_status == ParticipantCalendarStatus.VISIBLE:
            participant.calendar_status = ParticipantCalendarStatus.REMOVED; participant.removed_at = now; participant.lock_version += 1
    reminders = list(db.scalars(select(ActivityReminder).where(
        ActivityReminder.activity_id.in_([item.id for item in affected]), ActivityReminder.workspace_id == activity.workspace_id,
        ActivityReminder.user_id == actor.id,
    ).order_by(ActivityReminder.activity_id, ActivityReminder.id).with_for_update()))
    for reminder in reminders:
        reminder.is_enabled = False
        reminder.lock_version += 1
    for item in affected: item.lock_version += 1
    _flush(db)
    return activity


def temporal_state(activity: Activity, *, now: datetime | None = None) -> ActivityTemporalState:
    current = now or _now()
    if current < activity.starts_at: return "FUTURE"
    if current < activity.ends_at: return "IN_PROGRESS"
    return "PAST"


def activity_projection(db: Session, *, activity: Activity, actor_id: uuid.UUID) -> tuple[ActivityMaster | None, Category, User, list[tuple[ActivityParticipant, User]], ActivityTemporalState]:
    master = db.scalar(select(ActivityMaster).where(ActivityMaster.id == activity.activity_master_id, ActivityMaster.workspace_id == activity.workspace_id)) if activity.activity_master_id else None
    category_id = master.category_id if master else activity.custom_category_id
    category = db.scalar(select(Category).where(Category.id == category_id, Category.workspace_id == activity.workspace_id))
    organizer = db.scalar(select(User).where(User.id == activity.organizer_user_id))
    visible = [item for item in activity.participants if item.calendar_status == ParticipantCalendarStatus.VISIBLE]
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_([item.user_id for item in visible])))} if visible else {}
    if category is None or organizer is None:
        raise ActivityNotFoundError("Activity not found")
    return master, category, organizer, [(item, users[item.user_id]) for item in visible if item.user_id in users], temporal_state(activity)
