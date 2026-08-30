import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from app.services.v2_home import get_home_summary


def test_home_uses_one_local_date_and_fixed_batch_queries() -> None:
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    with patch("app.services.v2_home.list_my_calendar", side_effect=[[], []]) as calendar:
        result = get_home_summary(db, user_id=uuid.uuid4(), timezone_name="America/Lima", now=datetime(2026, 8, 30, 2, tzinfo=timezone.utc))
    assert result.local_date == date(2026, 8, 29)
    assert result.today == (0, 0, 0, 0)
    assert len(result.upcoming_days) == 7
    assert result.upcoming_days[0][0] == date(2026, 8, 30)
    assert calendar.call_args_list[0].kwargs["range_start"].date() == date(2026, 8, 29)
    assert all(call.kwargs["require_active_access"] is True for call in calendar.call_args_list)
    assert calendar.call_args_list[1].kwargs["future_only"] is True
    assert calendar.call_args_list[1].kwargs["limit"] == 5
    assert len(db.execute.call_args_list) == 6
    sql = [str(call.args[0]) for call in db.execute.call_args_list]
    assert all("workspace_members.status" in statement and "workspaces.lifecycle" in statement for statement in sql)
    assert "tasks.result IS NULL" in sql[0]
    assert "pending_items.is_active IS true" in sql[1] and "pending_items.progress <" in sql[1]
    assert "projects.is_active IS true" in sql[2] and "project_stages.progress <" in sql[2]


def test_home_counts_a_multi_day_activity_once_per_local_day_and_keeps_real_instant_order() -> None:
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    crossing = SimpleNamespace(activity=SimpleNamespace(
        starts_at=datetime(2026, 11, 1, 3, 30, tzinfo=timezone.utc),
        ends_at=datetime(2026, 11, 2, 6, 30, tzinfo=timezone.utc),
    ))
    later = SimpleNamespace(activity=SimpleNamespace(
        starts_at=datetime(2026, 11, 3, 15, tzinfo=timezone.utc),
        ends_at=datetime(2026, 11, 3, 16, tzinfo=timezone.utc),
    ))
    with patch("app.services.v2_home.list_my_calendar", side_effect=[[crossing], [crossing, later]]):
        result = get_home_summary(
            db, user_id=uuid.uuid4(), timezone_name="America/New_York",
            now=datetime(2026, 11, 1, 3, tzinfo=timezone.utc),
        )
    assert result.local_date == date(2026, 10, 31)
    assert result.today[3] == 1
    assert result.upcoming_days[0][0] == date(2026, 11, 1)
    assert result.upcoming_days[0][4] == 1
    assert result.upcoming_days[1][4] == 1
    assert result.upcoming_activities == [crossing, later]
