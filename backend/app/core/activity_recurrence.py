from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


class InvalidLocalActivityTimeError(ValueError):
    pass


def local_activity_datetime(*, local_date: date, local_time: time, timezone_name: str) -> datetime:
    """Resolve one unambiguous wall time to UTC without silently choosing a DST fold."""
    zone = ZoneInfo(timezone_name)
    naive = datetime.combine(local_date, local_time)
    candidates: set[datetime] = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        utc_value = aware.astimezone(timezone.utc)
        if utc_value.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.add(utc_value)
    if len(candidates) != 1:
        raise InvalidLocalActivityTimeError("Local Activity time is nonexistent or ambiguous")
    return candidates.pop()
