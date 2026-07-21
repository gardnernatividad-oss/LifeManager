import unittest

from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.models import TaskSeriesFrequency
from app.schemas.task_series import TaskSeriesCreate, TaskSeriesUpdate


class TaskSeriesSchemaTests(unittest.TestCase):
    def setUp(self) -> None: self.start = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
    def data(self, **changes: object) -> dict[str, object]:
        data = dict(title=" Series ", timezone="America/Lima", frequency="daily", starts_at=self.start)
        data.update(changes); return data

    def test_valid_daily_weekly_monthly_and_canonicalization(self) -> None:
        self.assertEqual(TaskSeriesCreate(**self.data()).interval, 1)
        weekly = TaskSeriesCreate(**self.data(frequency="weekly", weekdays=[5, 1, 5, 0]))
        self.assertEqual(weekly.weekdays, [0, 1, 5])
        monthly = TaskSeriesCreate(**self.data(frequency="monthly", month_day=31))
        self.assertEqual(monthly.month_day, 31)

    def test_invalid_timezone_datetime_range_and_shapes(self) -> None:
        invalid = (
            self.data(timezone="+05:00"), self.data(timezone="Invalid/Zone"),
            self.data(starts_at=datetime(2026, 1, 1)), self.data(ends_at=datetime(2026, 1, 2)),
            self.data(ends_at=self.start), self.data(interval=0), self.data(interval=366),
            self.data(frequency="weekly", weekdays=[]), self.data(frequency="weekly", weekdays=[7]),
            self.data(frequency="weekly", weekdays=[1], month_day=2),
            self.data(frequency="monthly"), self.data(frequency="monthly", month_day=32),
            self.data(weekdays=[1]), self.data(month_day=1), self.data(extra=True),
        )
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError): TaskSeriesCreate.model_validate(data)

    def test_update_null_and_fragment_semantics(self) -> None:
        self.assertEqual(TaskSeriesUpdate().model_dump(exclude_unset=True), {})
        self.assertEqual(TaskSeriesUpdate(description=None, ends_at=None, weekdays=None).model_dump(exclude_unset=True), {"description": None, "ends_at": None, "weekdays": None})
        for field in ("title", "timezone", "frequency", "interval", "starts_at"):
            with self.subTest(field=field), self.assertRaises(ValidationError): TaskSeriesUpdate.model_validate({field: None})


if __name__ == "__main__": unittest.main()
