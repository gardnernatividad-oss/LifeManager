from datetime import date

import pytest

from app.core.recurrence import recurrence_dates
from app.models.enums import GenerationPattern


def test_daily_is_inclusive() -> None:
    assert recurrence_dates(pattern=GenerationPattern.DAILY, date_from=date(2028, 2, 28), date_until=date(2028, 3, 1)) == [date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1)]


def test_selected_weekdays_use_monday_zero() -> None:
    assert recurrence_dates(pattern=GenerationPattern.WEEKLY, date_from=date(2026, 8, 17), date_until=date(2026, 8, 23), weekdays=[0, 4]) == [date(2026, 8, 17), date(2026, 8, 21)]


def test_monthly_anchors_fallback_and_deduplicate() -> None:
    assert recurrence_dates(pattern=GenerationPattern.MONTHLY, date_from=date(2028, 1, 1), date_until=date(2028, 3, 31), month_days=[29, 30, 31]) == [date(2028, 1, 29), date(2028, 1, 30), date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 29), date(2028, 3, 30), date(2028, 3, 31)]


def test_monthly_days_two_and_six_respect_boundaries() -> None:
    assert recurrence_dates(pattern=GenerationPattern.MONTHLY, date_from=date(2026, 1, 4), date_until=date(2026, 3, 3), month_days=[2, 6]) == [date(2026, 1, 6), date(2026, 2, 2), date(2026, 2, 6), date(2026, 3, 2)]


def test_invalid_range_and_anchors_fail() -> None:
    with pytest.raises(ValueError):
        recurrence_dates(pattern=GenerationPattern.DAILY, date_from=date(2026, 2, 2), date_until=date(2026, 2, 1))
    with pytest.raises(ValueError):
        recurrence_dates(pattern=GenerationPattern.MONTHLY, date_from=date(2026, 1, 1), date_until=date(2026, 2, 1), month_days=[32])
