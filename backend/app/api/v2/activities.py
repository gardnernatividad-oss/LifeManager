import math
import uuid

from datetime import datetime

from fastapi import APIRouter, Query, Response, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from sqlalchemy import select

from app.models import Activity, ActivityMaster, Category, User
from app.models.enums import ParticipantCalendarStatus, WorkspaceKind
from app.schemas.v2_activity import ActivityCreate, ActivityListResponse, ActivityMutationScope, ActivityParticipantRead, ActivityRead, ActivityUpdate, ActivityVersion, RecurringActivityCreate, RecurringActivityCreateResponse
from app.services.v2_activity import (
    ActivityConflictError, ActivityNotFoundError, ActivityRecurrenceError, ActivityReferenceUnavailableError,
    activity_projection, create_activity, create_recurring_activities, delete_activity, get_activity, leave_activity,
    list_activities, temporal_state, update_activity,
)


router = APIRouter(prefix="/workspaces/{workspace_id}/activities", tags=["V2 Activities"])


def _raise(error: Exception) -> None:
    if isinstance(error, ActivityNotFoundError):
        raise V2APIError(status_code=404, code="ACTIVITY_NOT_FOUND", message="No se encontró la Actividad.") from error
    if isinstance(error, ActivityReferenceUnavailableError):
        raise V2APIError(status_code=404, code="ACTIVITY_REFERENCE_UNAVAILABLE", message="Una referencia de la Actividad no está disponible.") from error
    if isinstance(error, ActivityRecurrenceError):
        raise V2APIError(status_code=422, code="ACTIVITY_RECURRENCE_INVALID", message="La recurrencia o su horario local no es válido.") from error
    raise V2APIError(status_code=409, code="ACTIVITY_CONFLICT", message="La Actividad cambió o ya no admite esta acción.") from error


def _read(db: SessionDependency, activity: Activity, account: User, *, personal: bool, projection=None) -> ActivityRead:
    master, category, organizer, participants, state = projection or activity_projection(db, activity=activity, actor_id=account.id)
    mutable_future = state == "FUTURE" and activity.status == "SCHEDULED"
    participating = any(item.user_id == account.id and item.calendar_status == ParticipantCalendarStatus.VISIBLE for item, _ in participants)
    return ActivityRead(
        id=activity.id, workspace_id=activity.workspace_id,
        activity_master_id=activity.activity_master_id,
        activity_master_name=master.name if master else None,
        is_custom=master is None,
        custom_category_id=activity.custom_category_id,
        category_id=category.id, category_name=category.name,
        title=master.name if master else activity.title,
        organizer_user_id=organizer.id,
        organizer_display_name=f"{organizer.first_name} {organizer.last_name}".strip(), organizer_email=organizer.email,
        participants=[ActivityParticipantRead(user_id=user.id, display_name=f"{user.first_name} {user.last_name}".strip(), email=user.email, calendar_status=item.calendar_status) for item, user in participants],
        reminder_minutes_before=next((item.minutes_before for item in activity.reminders if item.is_enabled), None),
        starts_at=activity.starts_at, ends_at=activity.ends_at, status=activity.status,
        temporal_state=state, lock_version=activity.lock_version,
        is_generated=activity.generation_batch_id is not None,
        can_edit=mutable_future, can_delete=mutable_future,
        can_leave_participation=mutable_future and participating and not personal,
        created_at=activity.created_at, updated_at=activity.updated_at,
    )


def _list_projections(db: SessionDependency, activities: list[Activity]):
    master_ids = {item.activity_master_id for item in activities if item.activity_master_id is not None}
    masters = {item.id: item for item in db.scalars(select(ActivityMaster).where(ActivityMaster.id.in_(master_ids)))} if master_ids else {}
    category_ids = {masters[item.activity_master_id].category_id if item.activity_master_id in masters else item.custom_category_id for item in activities}
    categories = {item.id: item for item in db.scalars(select(Category).where(Category.id.in_(category_ids - {None})))}
    user_ids = {item.organizer_user_id for item in activities}
    for activity in activities:
        user_ids.update(participant.user_id for participant in activity.participants if participant.calendar_status == ParticipantCalendarStatus.VISIBLE)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    projections = {}
    for activity in activities:
        master = masters.get(activity.activity_master_id)
        category_id = master.category_id if master else activity.custom_category_id
        category, organizer = categories.get(category_id), users.get(activity.organizer_user_id)
        if category is None or organizer is None:
            raise ActivityNotFoundError("Activity not found")
        participants = [(item, users[item.user_id]) for item in activity.participants if item.calendar_status == ParticipantCalendarStatus.VISIBLE and item.user_id in users]
        projections[activity.id] = (master, category, organizer, participants, temporal_state(activity))
    return projections


def _write(db: SessionDependency, operation):
    try:
        result = operation()
        db.commit()
        if isinstance(result, list):
            for item in result:
                db.refresh(item)
        elif result is not None:
            db.refresh(result)
        return result
    except (ActivityNotFoundError, ActivityConflictError, ActivityReferenceUnavailableError, ActivityRecurrenceError) as error:
        db.rollback()
        _raise(error)
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
def create(workspace_id: uuid.UUID, activity_in: ActivityCreate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ActivityRead:
    del workspace_id
    activity = _write(db, lambda: create_activity(db, access=access, actor=account, activity_in=activity_in))
    return _read(db, activity, account, personal=access.workspace.kind == WorkspaceKind.PERSONAL)


@router.post("/recurring", response_model=RecurringActivityCreateResponse, status_code=status.HTTP_201_CREATED)
def create_recurring(
    workspace_id: uuid.UUID, activity_in: RecurringActivityCreate, db: SessionDependency,
    account: UsableAccount, access: ActiveWorkspaceMembership,
) -> RecurringActivityCreateResponse:
    del workspace_id
    activities = _write(db, lambda: create_recurring_activities(db, access=access, actor=account, activity_in=activity_in))
    personal = access.workspace.kind == WorkspaceKind.PERSONAL
    return RecurringActivityCreateResponse(
        created_count=len(activities),
        items=[_read(db, activity, account, personal=personal) for activity in activities],
    )


@router.get("", response_model=ActivityListResponse)
def index(
    workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    starts_from: datetime | None = None, starts_until: datetime | None = None,
    activity_master_id: uuid.UUID | None = None, category_id: uuid.UUID | None = None,
    organizer_user_id: uuid.UUID | None = None, participant_user_id: uuid.UUID | None = None,
    custom: bool | None = None,
) -> ActivityListResponse:
    for value in (starts_from, starts_until):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise V2APIError(status_code=422, code="INVALID_DATETIME", message="Las fechas deben incluir zona horaria.")
    if starts_from and starts_until and starts_from > starts_until:
        raise V2APIError(status_code=422, code="INVALID_DATE_RANGE", message="El rango de fechas no es válido.")
    items, total = list_activities(db, workspace_id=workspace_id, page=page, page_size=page_size, starts_from=starts_from, starts_until=starts_until, activity_master_id=activity_master_id, category_id=category_id, organizer_user_id=organizer_user_id, participant_user_id=participant_user_id, custom=custom)
    personal = access.workspace.kind == WorkspaceKind.PERSONAL
    projections = _list_projections(db, items)
    return ActivityListResponse(items=[_read(db, item, account, personal=personal, projection=projections[item.id]) for item in items], total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size))


@router.get("/{activity_id}", response_model=ActivityRead)
def detail(workspace_id: uuid.UUID, activity_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ActivityRead:
    try:
        return _read(db, get_activity(db, workspace_id=workspace_id, activity_id=activity_id), account, personal=access.workspace.kind == WorkspaceKind.PERSONAL)
    except ActivityNotFoundError as error:
        _raise(error)


@router.patch("/{activity_id}", response_model=ActivityRead)
def patch(workspace_id: uuid.UUID, activity_id: uuid.UUID, activity_in: ActivityUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ActivityRead:
    del workspace_id
    activity = _write(db, lambda: update_activity(db, access=access, activity_id=activity_id, activity_in=activity_in))
    return _read(db, activity, account, personal=access.workspace.kind == WorkspaceKind.PERSONAL)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(workspace_id: uuid.UUID, activity_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, lock_version: int = Query(ge=1), scope: ActivityMutationScope = Query(default="THIS")) -> Response:
    del workspace_id
    _write(db, lambda: delete_activity(db, access=access, actor=account, activity_id=activity_id, expected_version=lock_version, scope=scope))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{activity_id}/leave", response_model=ActivityRead)
def leave(workspace_id: uuid.UUID, activity_id: uuid.UUID, version_in: ActivityVersion, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> ActivityRead:
    del workspace_id
    if access.workspace.kind == WorkspaceKind.PERSONAL:
        raise V2APIError(status_code=409, code="ACTIVITY_CONFLICT", message="La Actividad no admite esta acción.")
    activity = _write(db, lambda: leave_activity(db, access=access, actor=account, activity_id=activity_id, expected_version=version_in.lock_version, scope=version_in.scope))
    return _read(db, activity, account, personal=False)
