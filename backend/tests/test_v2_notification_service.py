import uuid

from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.models import ReminderPreference, User
from app.models.enums import AccountStatus, ReminderType, ScheduleKind
from app.schemas.v2_notifications import NotificationPreferencesUpdate
from app.services.v2_notifications import (
    NotificationPreferenceConflictError,
    activity_reminder_is_still_eligible,
    generate_scheduled_jobs,
    get_preferences,
    scheduled_instant,
    update_preferences,
)


def test_defaults_are_deterministic_without_writing_on_read() -> None:
    db = MagicMock(); db.scalars.return_value.all.return_value = []
    rows = get_preferences(db, user_id=uuid.uuid4())
    assert [(row.reminder_type, row.is_enabled, row.local_time, row.weekdays) for row in rows] == [
        (ReminderType.DAILY_SUMMARY, True, time(7), None), (ReminderType.DAILY_REVIEW, True, time(21), None),
        (ReminderType.PENDING_FOLLOW_UP, True, time(22), [6]), (ReminderType.PROJECT_FOLLOW_UP, True, time(22, 30), [6]),
        (ReminderType.ACTIVITY_REMINDERS, True, None, None),
    ]
    db.add.assert_not_called(); db.flush.assert_not_called()


def test_update_rejects_stale_versions_before_mutating() -> None:
    db = MagicMock(); user_id = uuid.uuid4()
    rows = [ReminderPreference(user_id=user_id, reminder_type=kind, is_enabled=True, schedule_kind=config[0], local_time=config[1], weekdays=config[2], lock_version=2) for kind, config in __import__("app.services.v2_notifications", fromlist=["DEFAULTS"]).DEFAULTS.items()]
    db.scalars.return_value.all.return_value = rows
    payload = NotificationPreferencesUpdate.model_validate({
        "daily_summary": {"enabled": True, "local_time": "07:00", "lock_version": 1},
        "daily_review": {"enabled": True, "local_time": "21:00", "lock_version": 2},
        "pending_weekly": {"enabled": True, "local_time": "22:00", "weekday": 6, "lock_version": 2},
        "project_weekly": {"enabled": True, "local_time": "22:30", "weekday": 6, "lock_version": 2},
        "activity_reminders": {"enabled": True, "lock_version": 2},
    })
    with pytest.raises(NotificationPreferenceConflictError): update_preferences(db, user_id=user_id, preferences_in=payload)
    db.flush.assert_called_once()  # missing-row persistence boundary; no updated version was flushed
    assert all(row.lock_version == 2 for row in rows)


def test_dst_policy_moves_nonexistent_forward_and_uses_ambiguous_once() -> None:
    zone = ZoneInfo("America/New_York")
    assert scheduled_instant(date(2026, 3, 8), time(2, 30), zone) == datetime(2026, 3, 8, 7, tzinfo=timezone.utc)
    assert scheduled_instant(date(2026, 11, 1), time(1, 30), zone) == datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)
    assert scheduled_instant(date(2026, 8, 30), time(7), ZoneInfo("America/Lima")) == datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def test_scheduler_uses_one_user_query_one_preference_query_and_half_open_window() -> None:
    db = MagicMock(); user = User(id=uuid.uuid4(), timezone="America/Lima", account_status=AccountStatus.ACTIVE)
    db.scalars.side_effect = [MagicMock(all=lambda: [user]), MagicMock(all=lambda: []), MagicMock(all=lambda: [])]
    activity_result = MagicMock(); activity_result.all.return_value = []
    insert_result = MagicMock(); insert_result.scalars.return_value.all.return_value = [uuid.uuid4() for _ in range(4)]
    db.execute.side_effect = [activity_result, insert_result]
    count = generate_scheduled_jobs(db, window_start=datetime(2026, 8, 30, 12, tzinfo=timezone.utc), window_end=datetime(2026, 8, 31, 3, 1, tzinfo=timezone.utc))
    assert count == 4
    assert db.scalars.call_count == 3
    db.flush.assert_called_once()


def test_activity_reminder_revalidates_domain_and_global_preference() -> None:
    db = MagicMock()
    reminder_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db.scalar.side_effect = [reminder_id, None]

    assert activity_reminder_is_still_eligible(
        db,
        reminder_id=reminder_id,
        user_id=user_id,
        now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc),
    )

    eligibility_sql = str(db.scalar.call_args_list[0].args[0])
    assert "activity_reminders" in eligibility_sql
    assert "activity_participants" in eligibility_sql
    assert "activities" in eligibility_sql
    assert "LEFT OUTER JOIN activity_participants" in eligibility_sql
    assert "activities.organizer_user_id = activity_reminders.user_id" in eligibility_sql
    assert "workspace_members" in eligibility_sql
    assert "activities.starts_at >" in eligibility_sql
    assert "activity_reminders.is_enabled IS true" in eligibility_sql
    preference_sql = str(db.scalar.call_args_list[1].args[0])
    assert "reminder_preferences" in preference_sql
