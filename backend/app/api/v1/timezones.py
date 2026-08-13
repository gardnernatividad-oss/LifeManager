from zoneinfo import available_timezones

from fastapi import APIRouter

from app.api.dependencies import CurrentUser
from app.schemas.timezone import TimezoneListResponse


router = APIRouter(prefix="/timezones", tags=["Configuration"])


@router.get("", response_model=TimezoneListResponse)
def list_timezones(_current_user: CurrentUser) -> TimezoneListResponse:
    return TimezoneListResponse(items=sorted(available_timezones()))
