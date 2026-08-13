from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezoneError(ValueError):
    pass


def local_today(timezone_name: str, *, now: datetime | None = None) -> date:
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidTimezoneError("User timezone is invalid") from error
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(zone).date()
