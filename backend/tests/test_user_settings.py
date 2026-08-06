import unittest
import uuid

from datetime import time
from unittest.mock import MagicMock

from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Session

from app.models import User, UserSettings, WeekStartsOn
from app.schemas.user_settings import UserSettingsReplace
from app.services.user_settings_service import get_or_create_user_settings, replace_user_settings


class UserSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4())

    @staticmethod
    def payload(**changes: object) -> UserSettingsReplace:
        values = dict(
            timezone="America/New_York", locale=" en-US ", week_starts_on="SUNDAY",
            daily_form_reminders_enabled=False, task_due_reminders_enabled=True,
            task_overdue_reminders_enabled=False, daily_form_reminder_time="08:30:00",
            task_due_reminder_minutes=1440,
        )
        values.update(changes); return UserSettingsReplace.model_validate(values)

    def test_model_constraints_defaults_fk_and_one_to_one_relationship(self) -> None:
        table = UserSettings.__table__
        self.assertIn("uq_user_settings_user_id", {item.name for item in table.constraints if isinstance(item, UniqueConstraint)})
        checks = {item.name for item in table.constraints if isinstance(item, CheckConstraint)}
        self.assertEqual(checks, {"ck_user_settings_timezone_not_blank", "ck_user_settings_locale_not_blank", "ck_user_settings_task_due_minutes_range"})
        self.assertEqual(next(iter(table.c.user_id.foreign_keys)).ondelete, "CASCADE")
        self.assertFalse(User.settings.property.uselist); self.assertIn("delete-orphan", User.settings.property.cascade)
        self.assertTrue(User.settings.property.single_parent)
        self.assertEqual(table.c.timezone.default.arg, "America/Lima"); self.assertEqual(table.c.locale.default.arg, "es-PE")
        self.assertEqual(table.c.task_due_reminder_minutes.default.arg, 60)

    def test_schema_validation_timezone_locale_week_time_minutes_and_extras(self) -> None:
        schema = self.payload()
        self.assertEqual(schema.locale, "en-US"); self.assertIs(schema.week_starts_on, WeekStartsOn.SUNDAY)
        self.assertEqual(schema.daily_form_reminder_time, time(8, 30)); self.assertEqual(schema.task_due_reminder_minutes, 1440)
        for timezone_value in ("UTC", "Europe/Madrid", "America/New_York"):
            self.assertEqual(self.payload(timezone=timezone_value).timezone, timezone_value)
        for changes in (
            {"timezone": "Bad/Zone"}, {"timezone": " "}, {"locale": " "},
            {"week_starts_on": "FRIDAY"}, {"task_due_reminder_minutes": -1},
            {"task_due_reminder_minutes": 1441}, {"user_id": uuid.uuid4()},
        ):
            values = self.payload().model_dump(mode="json"); values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError): UserSettingsReplace.model_validate(values)
        self.assertEqual(self.payload(task_due_reminder_minutes=0).task_due_reminder_minutes, 0)

    def test_first_get_creates_exact_defaults_and_repeated_get_reuses_row(self) -> None:
        self.db.scalar.return_value = None
        settings = get_or_create_user_settings(self.db, current_user=self.user)
        self.assertEqual(
            (settings.user_id, settings.timezone, settings.locale, settings.week_starts_on,
             settings.daily_form_reminders_enabled, settings.task_due_reminders_enabled,
             settings.task_overdue_reminders_enabled, settings.daily_form_reminder_time,
             settings.task_due_reminder_minutes),
            (self.user.id, "America/Lima", "es-PE", WeekStartsOn.MONDAY, True, True, True, time(9), 60),
        )
        self.db.add.assert_called_once_with(settings); self.db.flush.assert_called_once()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()
        self.db.reset_mock(); self.db.scalar.return_value = settings
        self.assertIs(get_or_create_user_settings(self.db, current_user=self.user), settings)
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()

    def test_put_creates_or_replaces_all_fields_preserving_identity_and_user(self) -> None:
        for existing in (None, UserSettings(id=uuid.uuid4(), user_id=self.user.id)):
            self.db.reset_mock(); self.db.scalar.return_value = existing
            original_id = existing.id if existing else None
            settings = replace_user_settings(self.db, current_user=self.user, settings_in=self.payload())
            if original_id: self.assertEqual(settings.id, original_id)
            self.assertEqual(settings.user_id, self.user.id); self.assertEqual(settings.locale, "en-US")
            self.assertEqual((settings.daily_form_reminders_enabled, settings.task_due_reminders_enabled, settings.task_overdue_reminders_enabled), (False, True, False))
            self.db.flush.assert_called_once(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()
            statement = self.db.scalar.call_args.args[0]
            self.assertIn(self.user.id, statement.compile().params.values())


if __name__ == "__main__":
    unittest.main()
