import unittest
import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.services.dashboard_service import (
    DashboardPermissionError,
    get_dashboard_summary,
)


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.now = datetime(2026, 7, 22, 15, 30, tzinfo=timezone.utc)
        self.membership = WorkspaceMember(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.MEMBER,
        )

    def member(self, value: object = ...):
        result = self.membership if value is ... else value
        return patch(
            "app.services.dashboard_service.get_workspace_membership",
            return_value=result,
        )

    def aggregate(self, values: dict[str, int]) -> None:
        row = MagicMock()
        row._mapping = values
        self.db.execute.return_value.one.return_value = row

    @staticmethod
    def counters(**changes: int) -> dict[str, int]:
        values = {
            "pending_tasks": 0,
            "scheduled_tasks": 0,
            "completed_tasks": 0,
            "not_completed_tasks": 0,
            "cancelled_tasks": 0,
            "total_tasks": 0,
            "tasks_due_today": 0,
            "tasks_due_next_7_days": 0,
            "overdue_tasks": 0,
        }
        values.update(changes)
        return values

    def test_empty_workspace_returns_zero_summary_without_writes(self) -> None:
        self.aggregate(self.counters())
        with self.member(), patch("app.services.dashboard_service._utc_now", return_value=self.now):
            summary = get_dashboard_summary(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )
        self.assertEqual(summary.model_dump(), self.counters())
        self.db.execute.assert_called_once()
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called(); self.db.delete.assert_not_called()

    def test_mixed_states_return_every_counter_from_one_aggregate_query(self) -> None:
        expected = self.counters(
            pending_tasks=4,
            scheduled_tasks=3,
            completed_tasks=5,
            not_completed_tasks=2,
            cancelled_tasks=1,
            total_tasks=15,
            tasks_due_today=2,
            tasks_due_next_7_days=3,
            overdue_tasks=4,
        )
        self.aggregate(expected)
        with self.member(), patch("app.services.dashboard_service._utc_now", return_value=self.now):
            summary = get_dashboard_summary(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.assertEqual(summary.model_dump(), expected)
        statement = self.db.execute.call_args.args[0]
        sql = str(statement)
        params = tuple(statement.compile().params.values())
        self.assertEqual(sql.count("FILTER (WHERE"), 8)
        self.assertIn("tasks.workspace_id", sql)
        self.assertIn(self.workspace_id, params)
        self.assertIn(self.now, params)
        self.assertIn(datetime(2026, 7, 22, tzinfo=timezone.utc), params)
        self.assertIn(datetime(2026, 7, 23, tzinfo=timezone.utc), params)
        self.assertIn(self.now + timedelta(days=7), params)
        self.assertNotIn("ORDER BY", sql); self.assertNotIn("LIMIT", sql)

    def test_nonmember_is_denied_before_aggregation(self) -> None:
        with self.member(None), self.assertRaises(DashboardPermissionError):
            get_dashboard_summary(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.db.execute.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
