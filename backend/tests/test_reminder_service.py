import unittest
import uuid

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import DailyFormDefinition, Task, User, UserSettings, WeekStartsOn, Workspace, WorkspaceMember, WorkspaceSettings
from app.models.workspace_member import WorkspaceRole
from app.schemas.reminder import ReminderType
from app.services.reminder_service import ReminderPermissionError, ReminderTimezoneError, evaluate_reminders


class ReminderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.workspace = Workspace(id=self.workspace_id, name="Home", timezone="America/Lima")
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)
        self.evaluated = datetime(2026, 7, 22, 14, tzinfo=timezone.utc)

    def member(self, value: object = ...):
        return patch("app.services.reminder_service.get_workspace_membership", return_value=self.membership if value is ... else value)

    def task(self, scheduled_at: datetime, **changes: object) -> Task:
        values = dict(
            id=uuid.uuid4(), workspace_id=self.workspace_id, created_by_id=self.user.id,
            task_series_id=None, category_id=None, project_id=None, title="Task",
            scheduled_at=scheduled_at, outcome=None, resolved_at=None,
        )
        values.update(changes); return Task(**values)

    def evaluate(self, *, scalar_values: list[object], tasks: list[Task], evaluated: datetime | None = None,
                 workspace: Workspace | None = None, workspace_settings: WorkspaceSettings | None = None,
                 user_settings: UserSettings | None = None):
        self.db.scalar.side_effect = [workspace or self.workspace, workspace_settings, user_settings, *scalar_values]
        rows = MagicMock(); rows.all.return_value = tasks; self.db.scalars.return_value = rows
        with self.member():
            return evaluate_reminders(
                self.db, workspace_id=self.workspace_id, current_user=self.user,
                evaluated_at=evaluated or self.evaluated,
            )

    def test_empty_result_is_successful_read_only_and_scoped(self) -> None:
        result = self.evaluate(scalar_values=[None], tasks=[])
        self.assertEqual(result.reminder_count, 0); self.assertEqual(result.reminders, [])
        statement = self.db.scalars.call_args.args[0]; sql = str(statement); params = tuple(statement.compile().params.values())
        for value in (self.workspace_id, self.user.id): self.assertIn(value, params)
        self.assertIn("tasks.outcome IS NULL", sql); self.assertIn("tasks.scheduled_at IS NOT NULL", sql)
        self.db.add.assert_not_called(); self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_form_threshold_before_exact_after_and_matching_submission(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        cases = (
            (datetime(2026, 7, 22, 13, 59, tzinfo=timezone.utc), [definition], 0),
            (datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc), [definition, None], 1),
            (datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc), [definition, None], 1),
            (datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc), [definition, uuid.uuid4()], 0),
        )
        for evaluated, scalars, expected in cases:
            self.db.reset_mock()
            with self.subTest(evaluated=evaluated): result = self.evaluate(scalar_values=scalars, tasks=[], evaluated=evaluated)
            form_items = [item for item in result.reminders if item.reminder_type is ReminderType.DAILY_FORM_REQUIRED]
            self.assertEqual(len(form_items), expected)
            if form_items:
                self.assertEqual(form_items[0].scheduled_for, datetime(2026, 7, 22, 14, tzinfo=timezone.utc))
                self.assertEqual(form_items[0].metadata["definition_id"], str(definition.id))

    def test_submission_lookup_is_scoped_to_user_date_workspace_and_definition(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        self.evaluate(scalar_values=[definition, None], tasks=[])
        statement = self.db.scalar.call_args.args[0]; params = tuple(statement.compile().params.values())
        for value in (self.workspace_id, self.user.id, date(2026, 7, 22), definition.id): self.assertIn(value, params)

    def test_due_overdue_boundaries_minutes_series_metadata_and_ordering(self) -> None:
        series_id = uuid.uuid4()
        due_later = self.task(self.evaluated + timedelta(minutes=60), id=uuid.UUID(int=5), task_series_id=series_id, title="Due 60")
        due_soon = self.task(self.evaluated + timedelta(minutes=10, seconds=59), id=uuid.UUID(int=4), title="Due soon")
        exact = self.task(self.evaluated, id=uuid.UUID(int=3), title="Exact")
        overdue_late = self.task(self.evaluated - timedelta(minutes=5, seconds=59), id=uuid.UUID(int=2), title="Overdue")
        overdue_early = self.task(self.evaluated - timedelta(hours=2), id=uuid.UUID(int=1), title="Old")
        result = self.evaluate(scalar_values=[None], tasks=[due_later, exact, overdue_late, due_soon, overdue_early])
        self.assertEqual([item.reminder_type for item in result.reminders], [ReminderType.TASK_OVERDUE] * 3 + [ReminderType.TASK_DUE] * 2)
        self.assertEqual([item.entity_id for item in result.reminders], [overdue_early.id, overdue_late.id, exact.id, due_soon.id, due_later.id])
        by_id = {item.entity_id: item for item in result.reminders}
        self.assertEqual(by_id[due_later.id].metadata["minutes_until_due"], 60)
        self.assertEqual(by_id[due_soon.id].metadata["minutes_until_due"], 10)
        self.assertEqual(by_id[exact.id].metadata["minutes_overdue"], 0)
        self.assertEqual(by_id[overdue_late.id].metadata["minutes_overdue"], 5)
        self.assertEqual(by_id[due_later.id].metadata["task_series_id"], str(series_id))
        self.assertEqual(result.reminder_count, len(result.reminders))

    def test_workspace_timezone_midnight_and_dst_are_applied(self) -> None:
        result = self.evaluate(scalar_values=[None], tasks=[], evaluated=datetime(2026, 7, 22, 3, tzinfo=timezone.utc))
        self.assertEqual(result.local_date, date(2026, 7, 21))
        new_york = Workspace(id=self.workspace_id, name="NY", timezone="America/New_York")
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        self.db.reset_mock()
        result = self.evaluate(scalar_values=[definition, None], tasks=[], workspace=new_york, evaluated=datetime(2026, 3, 8, 13, tzinfo=timezone.utc))
        self.assertEqual(result.local_date, date(2026, 3, 8))
        self.assertEqual(result.reminders[0].scheduled_for, datetime(2026, 3, 8, 13, tzinfo=timezone.utc))

    def test_nonmember_precedes_queries_and_invalid_persisted_timezone_fails(self) -> None:
        with self.member(None), self.assertRaises(ReminderPermissionError):
            evaluate_reminders(self.db, workspace_id=self.workspace_id, current_user=self.user, evaluated_at=self.evaluated)
        self.db.scalar.assert_not_called(); self.db.scalars.assert_not_called()
        self.db.reset_mock(); invalid = Workspace(id=self.workspace_id, name="Bad", timezone="Invalid/Zone"); self.db.scalar.side_effect = [invalid, None, None]
        with self.member(), self.assertRaises(ReminderTimezoneError):
            evaluate_reminders(self.db, workspace_id=self.workspace_id, current_user=self.user, evaluated_at=self.evaluated)
        self.db.scalars.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_effective_settings_timezone_threshold_and_read_only_fallbacks(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        workspace_settings = WorkspaceSettings(
            workspace_id=self.workspace_id, timezone="America/New_York", daily_form_enabled=True,
            daily_form_reminder_time=time(8), daily_task_generation_enabled=True,
            week_starts_on=WeekStartsOn.MONDAY,
        )
        user_settings = UserSettings(
            user_id=self.user.id, timezone="Europe/Madrid", locale="es-PE",
            week_starts_on=WeekStartsOn.MONDAY, daily_form_reminders_enabled=True,
            task_due_reminders_enabled=True, task_overdue_reminders_enabled=True,
            daily_form_reminder_time=time(10), task_due_reminder_minutes=30,
        )
        result = self.evaluate(
            scalar_values=[definition, None], tasks=[], workspace_settings=workspace_settings,
            user_settings=user_settings, evaluated=datetime(2026, 7, 22, 14, tzinfo=timezone.utc),
        )
        self.assertEqual(result.timezone, "America/New_York")
        self.assertEqual(result.reminders[0].scheduled_for, datetime(2026, 7, 22, 14, tzinfo=timezone.utc))
        self.db.add.assert_not_called(); self.db.flush.assert_not_called(); self.db.delete.assert_not_called()

    def test_workspace_reminder_time_applies_without_user_settings_and_invalid_override_fails(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        settings = WorkspaceSettings(workspace_id=self.workspace_id, timezone="America/Lima", daily_form_enabled=True, daily_form_reminder_time=time(8), daily_task_generation_enabled=True, week_starts_on=WeekStartsOn.MONDAY)
        result = self.evaluate(scalar_values=[definition, None], tasks=[], workspace_settings=settings, evaluated=datetime(2026, 7, 22, 13, tzinfo=timezone.utc))
        self.assertEqual(result.reminders[0].scheduled_for, datetime(2026, 7, 22, 13, tzinfo=timezone.utc))
        settings.timezone = "Invalid/Zone"; self.db.reset_mock()
        with self.assertRaises(ReminderTimezoneError):
            self.evaluate(scalar_values=[], tasks=[], workspace_settings=settings)

    def test_disabled_form_flags_skip_form_queries(self) -> None:
        for workspace_enabled, user_enabled in ((False, True), (True, False)):
            ws = WorkspaceSettings(workspace_id=self.workspace_id, timezone="America/Lima", daily_form_enabled=workspace_enabled, daily_form_reminder_time=time(9), daily_task_generation_enabled=True, week_starts_on=WeekStartsOn.MONDAY)
            user = UserSettings(user_id=self.user.id, timezone="America/Lima", locale="es-PE", week_starts_on=WeekStartsOn.MONDAY, daily_form_reminders_enabled=user_enabled, task_due_reminders_enabled=False, task_overdue_reminders_enabled=False, daily_form_reminder_time=time(9), task_due_reminder_minutes=60)
            self.db.reset_mock()
            result = self.evaluate(scalar_values=[], tasks=[], workspace_settings=ws, user_settings=user)
            self.assertEqual(result.reminders, []); self.assertEqual(self.db.scalar.call_count, 3); self.db.scalars.assert_not_called()

    def test_task_flags_and_configured_windows_are_independent(self) -> None:
        overdue = self.task(self.evaluated)
        due_30 = self.task(self.evaluated + timedelta(minutes=30))
        due_beyond = self.task(self.evaluated + timedelta(minutes=31))
        for due, overdue_flag, minutes, tasks, expected in (
            (False, True, 30, [overdue], [ReminderType.TASK_OVERDUE]),
            (True, False, 30, [due_30], [ReminderType.TASK_DUE]),
            (True, True, 0, [overdue], [ReminderType.TASK_OVERDUE]),
            (True, False, 1440, [due_30], [ReminderType.TASK_DUE]),
        ):
            settings = UserSettings(user_id=self.user.id, timezone="America/Lima", locale="es-PE", week_starts_on=WeekStartsOn.MONDAY, daily_form_reminders_enabled=False, task_due_reminders_enabled=due, task_overdue_reminders_enabled=overdue_flag, daily_form_reminder_time=time(9), task_due_reminder_minutes=minutes)
            self.db.reset_mock(); result = self.evaluate(scalar_values=[], tasks=tasks, user_settings=settings)
            self.assertEqual([item.reminder_type for item in result.reminders], expected)
        settings.task_due_reminder_minutes = 30
        self.db.reset_mock(); result = self.evaluate(scalar_values=[], tasks=[due_30], user_settings=settings)
        self.assertEqual(result.reminder_count, 1)
        params = tuple(self.db.scalars.call_args.args[0].compile().params.values())
        self.assertIn(self.evaluated + timedelta(minutes=30), params)


if __name__ == "__main__":
    unittest.main()
