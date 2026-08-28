import uuid

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, status

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.models.enums import CalendarVisibility
from app.schemas.v2_calendar import (
    CalendarBusyBlock, CalendarComparisonAvailability, CalendarComparisonDetail,
    CalendarComparisonDetails, CalendarComparisonHidden, CalendarComparisonResponse,
    CalendarVisibilityRead, CalendarVisibilityUpdate,
)
from app.services.v2_calendar_comparison import (
    CalendarComparisonNotFoundError, CalendarVisibilityConflictError,
    compare_calendar, get_calendar_visibility, update_calendar_visibility,
)


router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["V2 Calendar Comparison"])


def _validate_range(range_start: datetime, range_end: datetime) -> None:
    if any(value.tzinfo is None or value.utcoffset() is None for value in (range_start, range_end)):
        raise V2APIError(status_code=422, code="INVALID_CALENDAR_RANGE", message="El rango debe incluir zona horaria.")
    if range_end <= range_start or range_end - range_start > timedelta(days=366):
        raise V2APIError(status_code=422, code="INVALID_CALENDAR_RANGE", message="El rango de calendario no es válido.")


@router.get("/calendar-comparison", response_model=CalendarComparisonResponse)
def calendar_comparison(
    workspace_id: uuid.UUID, target_user_id: uuid.UUID,
    db: SessionDependency, account: UsableAccount,
    range_start: datetime = Query(alias="from"), range_end: datetime = Query(alias="to"),
) -> CalendarComparisonResponse:
    _validate_range(range_start, range_end)
    try:
        result = compare_calendar(
            db, workspace_id=workspace_id, viewer_id=account.id, target_id=target_user_id,
            range_start=range_start, range_end=range_end, now=datetime.now(timezone.utc),
        )
    except CalendarComparisonNotFoundError as error:
        raise V2APIError(status_code=404, code="CALENDAR_COMPARISON_NOT_FOUND", message="No se encontró el calendario compartido.") from error
    if result.visibility == CalendarVisibility.HIDE:
        return CalendarComparisonHidden(visibility=result.visibility)
    if result.visibility == CalendarVisibility.AVAILABILITY_ONLY:
        return CalendarComparisonAvailability(
            visibility=result.visibility,
            busy_blocks=[CalendarBusyBlock(starts_at=item.starts_at, ends_at=item.ends_at) for item in result.busy_blocks],
        )
    return CalendarComparisonDetails(
        visibility=result.visibility,
        detailed_events=[CalendarComparisonDetail(
            activity_name=item.activity.title, starts_at=item.activity.starts_at,
            ends_at=item.activity.ends_at, temporal_state=item.temporal_state,
        ) for item in result.events],
    )


@router.get("/calendar-visibility", response_model=CalendarVisibilityRead)
def own_calendar_visibility(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount) -> CalendarVisibilityRead:
    try:
        membership = get_calendar_visibility(db, workspace_id=workspace_id, user_id=account.id)
    except CalendarComparisonNotFoundError as error:
        raise V2APIError(status_code=404, code="CALENDAR_VISIBILITY_NOT_FOUND", message="No se encontró la configuración de calendario.") from error
    return CalendarVisibilityRead(visibility=membership.calendar_visibility, lock_version=membership.lock_version)


@router.patch("/calendar-visibility", response_model=CalendarVisibilityRead)
def set_own_calendar_visibility(
    workspace_id: uuid.UUID, payload: CalendarVisibilityUpdate,
    db: SessionDependency, account: UsableAccount,
) -> CalendarVisibilityRead:
    try:
        membership = update_calendar_visibility(
            db, workspace_id=workspace_id, user_id=account.id,
            visibility=payload.visibility, expected_lock_version=payload.lock_version,
        )
        db.commit()
        db.refresh(membership)
    except CalendarComparisonNotFoundError as error:
        db.rollback()
        raise V2APIError(status_code=404, code="CALENDAR_VISIBILITY_NOT_FOUND", message="No se encontró la configuración de calendario.") from error
    except CalendarVisibilityConflictError as error:
        db.rollback()
        raise V2APIError(status_code=status.HTTP_409_CONFLICT, code="CALENDAR_VISIBILITY_CONFLICT", message="La configuración cambió. Actualiza e intenta nuevamente.") from error
    except Exception:
        db.rollback()
        raise
    return CalendarVisibilityRead(visibility=membership.calendar_visibility, lock_version=membership.lock_version)
