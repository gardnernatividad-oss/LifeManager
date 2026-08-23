from calendar import monthrange
from datetime import date, timedelta

from app.models.enums import GenerationPattern


def recurrence_dates(*, pattern: GenerationPattern, date_from: date, date_until: date,
                     weekdays: list[int] | None = None,
                     month_days: list[int] | None = None) -> list[date]:
    """Return finite, inclusive, ordered and deduplicated recurrence dates."""
    if date_until < date_from:
        raise ValueError("date_until must be on or after date_from")
    if pattern is GenerationPattern.DAILY:
        return [date_from + timedelta(days=i) for i in range((date_until - date_from).days + 1)]
    if pattern is GenerationPattern.WEEKLY:
        anchors = set(weekdays or [])
        if not anchors or any(day < 0 or day > 6 for day in anchors):
            raise ValueError("weekdays must contain values from 0 through 6")
        return [candidate for i in range((date_until - date_from).days + 1)
                if (candidate := date_from + timedelta(days=i)).weekday() in anchors]
    if pattern is GenerationPattern.MONTHLY:
        anchors = sorted(set(month_days or []))
        if not anchors or any(day < 1 or day > 31 for day in anchors):
            raise ValueError("month_days must contain values from 1 through 31")
        result: set[date] = set()
        year, month = date_from.year, date_from.month
        while (year, month) <= (date_until.year, date_until.month):
            last = monthrange(year, month)[1]
            result.update(candidate for anchor in anchors
                          if date_from <= (candidate := date(year, month, min(anchor, last))) <= date_until)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return sorted(result)
    raise ValueError("unsupported recurrence pattern")
