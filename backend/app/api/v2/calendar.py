from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.schemas.v2_calendar import CalendarActivityRead, CalendarPersonRead, CalendarWorkspaceRead, MyCalendarResponse
from app.services.v2_calendar import CalendarActivityProjection, list_my_calendar


router = APIRouter(prefix="/calendar", tags=["V2 Calendar"])


def _person(user) -> CalendarPersonRead:
    return CalendarPersonRead(user_id=user.id, display_name=f"{user.first_name} {user.last_name}".strip(), email=user.email)


def _read(value: CalendarActivityProjection) -> CalendarActivityRead:
    return CalendarActivityRead(
        activity_id=value.activity.id,
        workspace=CalendarWorkspaceRead(id=value.workspace.id, name=value.workspace.name, kind=value.workspace.kind),
        activity_name=value.activity.title,
        category_name=value.category.name,
        starts_at=value.activity.starts_at, ends_at=value.activity.ends_at,
        organizer=_person(value.organizer), participants=[_person(user) for user in value.participants],
        status=value.activity.status, temporal_state=value.temporal_state,
        lock_version=value.activity.lock_version,
        can_edit=value.can_edit, can_delete=value.can_delete,
        can_leave_participation=value.can_leave_participation,
    )


@router.get("/me", response_model=MyCalendarResponse)
def my_calendar(
    db: SessionDependency, account: UsableAccount,
    range_start: datetime = Query(alias="from"), range_end: datetime = Query(alias="to"),
) -> MyCalendarResponse:
    if any(value.tzinfo is None or value.utcoffset() is None for value in (range_start, range_end)):
        raise V2APIError(status_code=422, code="INVALID_CALENDAR_RANGE", message="El rango debe incluir zona horaria.")
    if range_end <= range_start or range_end - range_start > timedelta(days=366):
        raise V2APIError(status_code=422, code="INVALID_CALENDAR_RANGE", message="El rango de calendario no es válido.")
    now = datetime.now(timezone.utc)
    return MyCalendarResponse(items=[_read(item) for item in list_my_calendar(
        db, user_id=account.id, range_start=range_start, range_end=range_end, now=now,
    )])
