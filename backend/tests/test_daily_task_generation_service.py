import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Task, TaskSeries, TaskSeriesFrequency, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.services.daily_task_generation_service import generate_daily_tasks
from app.services.task_series_service import TaskSeriesPermissionError


class DailyTaskGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.day = date(2026, 7, 22); self.generated_at = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)

    def series(self, **changes: object) -> TaskSeries:
        values = dict(
            id=uuid.uuid4(), workspace_id=self.workspace_id, created_by_id=self.user.id,
            category_id=None, project_id=None, title="Recurring", description="Copy",
            timezone="America/Lima", frequency=TaskSeriesFrequency.DAILY, interval=1,
            weekdays=None, month_day=None, starts_at=datetime(2026, 7, 1, 14, tzinfo=timezone.utc),
            ends_at=None, is_active=True,
        )
        values.update(changes); return TaskSeries(**values)

    def task(self, series: TaskSeries, task_id: uuid.UUID | None = None) -> Task:
        return Task(
            id=task_id or uuid.uuid4(), workspace_id=series.workspace_id,
            created_by_id=series.created_by_id, category_id=series.category_id,
            project_id=series.project_id, task_series_id=series.id, title=series.title,
            description=series.description, scheduled_at=datetime(2026, 7, 22, 14, tzinfo=timezone.utc),
            outcome=None, resolved_at=None,
        )

    def member(self, value: object = ...):
        return patch("app.services.daily_task_generation_service.get_workspace_membership", return_value=self.membership if value is ... else value)

    def series_result(self, items: list[TaskSeries]) -> MagicMock:
        result = MagicMock(); result.all.return_value = items; return result

    def test_one_eligible_series_creates_mapped_task_and_flush_is_delegated(self) -> None:
        series = self.series(category_id=uuid.uuid4(), project_id=uuid.uuid4()); task = self.task(series)
        self.db.scalars.return_value = self.series_result([series])
        with self.member(), patch("app.services.daily_task_generation_service.task_materialization_service._candidate_datetimes", return_value=[task.scheduled_at]), patch(
            "app.services.daily_task_generation_service.task_materialization_service._materialize", return_value=[task],
        ) as materialize, patch("app.services.daily_task_generation_service._utc_now", return_value=self.generated_at):
            result = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
        self.assertEqual((result.eligible_series_count, result.created_task_count, result.skipped_existing_count), (1, 1, 0))
        self.assertEqual(result.created_task_ids, [task.id]); self.assertEqual(result.generated_at, self.generated_at)
        self.assertEqual((task.title, task.description, task.category_id, task.project_id, task.created_by_id), (series.title, series.description, series.category_id, series.project_id, series.created_by_id))
        materialize.assert_called_once(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_multiple_mixed_series_count_created_and_existing_deterministically(self) -> None:
        first, second, third = self.series(), self.series(), self.series()
        early_id, late_id = uuid.UUID(int=1), uuid.UUID(int=2)
        early, late = self.task(first, early_id), self.task(second, late_id)
        early.scheduled_at = datetime(2026, 7, 22, 13, tzinfo=timezone.utc)
        self.db.scalars.return_value = self.series_result([first, second, third])
        with self.member(), patch("app.services.daily_task_generation_service.task_materialization_service._candidate_datetimes", side_effect=[[early.scheduled_at], [late.scheduled_at], [self.generated_at]]), patch(
            "app.services.daily_task_generation_service.task_materialization_service._materialize", side_effect=[[early], [late], []],
        ), patch("app.services.daily_task_generation_service._utc_now", return_value=self.generated_at):
            result = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
        self.assertEqual((result.eligible_series_count, result.created_task_count, result.skipped_existing_count), (3, 2, 1))
        self.assertEqual(result.created_task_ids, [early_id, late_id])

    def test_no_series_and_no_due_series_return_successful_zero_summary(self) -> None:
        for items, candidates in (([], []), ([self.series()], [])):
            self.db.reset_mock(); self.db.scalars.return_value = self.series_result(items)
            with self.subTest(count=len(items)), self.member(), patch(
                "app.services.daily_task_generation_service.task_materialization_service._candidate_datetimes", return_value=candidates,
            ), patch("app.services.daily_task_generation_service.task_materialization_service._materialize") as materialize:
                result = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
            self.assertEqual((result.eligible_series_count, result.created_task_count, result.skipped_existing_count), (0, 0, 0)); materialize.assert_not_called()

    def test_active_workspace_query_and_generation_date_scope(self) -> None:
        series = self.series(); self.db.scalars.return_value = self.series_result([series])
        with self.member(), patch("app.services.daily_task_generation_service.task_materialization_service._candidate_datetimes", return_value=[]) as candidates:
            generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
        statement = self.db.scalars.call_args.args[0]; sql = str(statement); params = tuple(statement.compile().params.values())
        self.assertIn("task_series.workspace_id", sql); self.assertIn("task_series.is_active IS true", sql); self.assertIn("ORDER BY task_series.id", sql)
        self.assertIn(self.workspace_id, params)
        window_start, window_end = candidates.call_args.args[1:]
        self.assertEqual(window_start.astimezone(timezone.utc), datetime(2026, 7, 22, 5, tzinfo=timezone.utc))
        self.assertEqual(window_end.date(), date(2026, 7, 23))

    def test_repeated_generation_is_idempotent_and_different_dates_use_distinct_windows(self) -> None:
        series = self.series(); task = self.task(series)
        self.db.scalars.return_value = self.series_result([series])
        windows: list[tuple[datetime, datetime]] = []

        def candidates(_series: TaskSeries, start: datetime, end: datetime) -> list[datetime]:
            windows.append((start, end)); return [task.scheduled_at]

        with self.member(), patch(
            "app.services.daily_task_generation_service.task_materialization_service._candidate_datetimes",
            side_effect=candidates,
        ), patch(
            "app.services.daily_task_generation_service.task_materialization_service._materialize",
            side_effect=[[task], [], [self.task(series)]],
        ):
            first = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
            repeated = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
            next_day = generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=date(2026, 7, 23), current_user=self.user)
        self.assertEqual((first.created_task_count, repeated.created_task_count, repeated.skipped_existing_count), (1, 0, 1))
        self.assertEqual(next_day.created_task_count, 1)
        self.assertEqual(windows[0], windows[1]); self.assertNotEqual(windows[1], windows[2])

    def test_nonmember_cannot_query_or_generate(self) -> None:
        with self.member(None), self.assertRaises(TaskSeriesPermissionError):
            generate_daily_tasks(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
        self.db.scalars.assert_not_called(); self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
