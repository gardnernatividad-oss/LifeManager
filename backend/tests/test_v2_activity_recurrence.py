from datetime import date, time, timezone

import pytest

from app.core.activity_recurrence import InvalidLocalActivityTimeError, local_activity_datetime
from app.schemas.v2_activity import RecurringActivityCreate


def test_local_activity_datetime_preserves_wall_time_in_iana_timezone() -> None:
    result = local_activity_datetime(local_date=date(2027, 1, 10), local_time=time(9), timezone_name="America/Lima")
    assert result.isoformat() == "2027-01-10T14:00:00+00:00" and result.tzinfo == timezone.utc


@pytest.mark.parametrize(("value_date", "value_time"), ((date(2027, 3, 14), time(2, 30)), (date(2027, 11, 7), time(1, 30))))
def test_local_activity_datetime_rejects_nonexistent_and_ambiguous_dst(value_date, value_time) -> None:
    with pytest.raises(InvalidLocalActivityTimeError):
        local_activity_datetime(local_date=value_date, local_time=value_time, timezone_name="America/New_York")


def test_recurring_activity_contract_supports_weekly_monday_zero() -> None:
    value = RecurringActivityCreate.model_validate({
        "activity_master_id": "11111111-1111-4111-8111-111111111111", "participant_user_ids": [],
        "start_time": "09:00", "end_time": "10:00", "timezone": "America/Lima",
        "recurrence": {"pattern": "WEEKLY", "date_from": "2027-01-04", "date_until": "2027-01-10", "weekdays": [0]},
    })
    assert value.recurrence.weekdays == [0]
