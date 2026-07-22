import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.services.dashboard_statistics_service import (
    DashboardStatisticsPermissionError,
    get_dashboard_statistics,
)


class DashboardStatisticsServiceTests(unittest.TestCase):
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
            "app.services.dashboard_statistics_service.get_workspace_membership",
            return_value=result,
        )

    def aggregate(self, **values: int) -> None:
        row = MagicMock()
        row._mapping = {
            "completed_tasks": 0,
            "not_completed_tasks": 0,
            "cancelled_tasks": 0,
            "resolved_tasks": 0,
            "pending_tasks": 0,
            "scheduled_tasks": 0,
            **values,
        }
        self.db.execute.return_value.one.return_value = row

    def test_empty_workspace_returns_zero_rate_without_division(self) -> None:
        self.aggregate()
        with self.member(), patch(
            "app.services.dashboard_statistics_service._utc_now",
            return_value=self.now,
        ):
            result = get_dashboard_statistics(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )
        self.assertEqual(
            result.model_dump(),
            {
                "completion_rate": 0.0,
                "completed_tasks": 0,
                "not_completed_tasks": 0,
                "cancelled_tasks": 0,
                "resolved_tasks": 0,
                "pending_tasks": 0,
                "scheduled_tasks": 0,
            },
        )

    def test_mixed_states_are_aggregated_and_completion_rate_is_rounded(self) -> None:
        self.aggregate(
            completed_tasks=1,
            not_completed_tasks=1,
            cancelled_tasks=1,
            resolved_tasks=3,
            pending_tasks=4,
            scheduled_tasks=2,
        )
        with self.member(), patch(
            "app.services.dashboard_statistics_service._utc_now",
            return_value=self.now,
        ):
            result = get_dashboard_statistics(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )
        self.assertEqual(result.completion_rate, 33.33)
        self.assertEqual(result.resolved_tasks, 3)
        statement = self.db.execute.call_args.args[0]
        sql = str(statement)
        params = tuple(statement.compile().params.values())
        self.assertEqual(sql.count("FILTER (WHERE"), 6)
        self.assertIn("tasks.workspace_id", sql)
        self.assertIn(self.workspace_id, params)
        self.assertIn(self.now, params)
        self.assertNotIn("ORDER BY", sql); self.assertNotIn("LIMIT", sql)

    def test_service_is_read_only_and_does_not_load_task_entities(self) -> None:
        self.aggregate(completed_tasks=2, resolved_tasks=2)
        with self.member(), patch(
            "app.services.dashboard_statistics_service._utc_now",
            return_value=self.now,
        ):
            result = get_dashboard_statistics(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.assertEqual(result.completion_rate, 100.0)
        self.db.execute.assert_called_once(); self.db.scalars.assert_not_called()
        self.db.add.assert_not_called(); self.db.flush.assert_not_called(); self.db.delete.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called(); self.db.refresh.assert_not_called()

    def test_nonmember_is_denied_before_aggregate_query(self) -> None:
        with self.member(None), self.assertRaises(DashboardStatisticsPermissionError):
            get_dashboard_statistics(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.db.execute.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
