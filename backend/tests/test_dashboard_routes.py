import unittest
import uuid

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User
from app.schemas.dashboard import DashboardStatistics, DashboardSummary
from app.services.dashboard_service import DashboardPermissionError
from app.services.dashboard_statistics_service import DashboardStatisticsPermissionError


class DashboardRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/dashboard"

    @staticmethod
    def summary() -> DashboardSummary:
        return DashboardSummary(
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

    @staticmethod
    def statistics() -> DashboardStatistics:
        return DashboardStatistics(
            completion_rate=62.5,
            completed_tasks=5,
            not_completed_tasks=2,
            cancelled_tasks=1,
            resolved_tasks=8,
            pending_tasks=4,
            scheduled_tasks=3,
        )

    def test_authenticated_summary_serializes_all_counters_and_is_read_only(self) -> None:
        summary = self.summary()
        with patch(
            "app.api.v1.dashboard.dashboard_service.get_dashboard_summary",
            return_value=summary,
        ) as service:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), summary.model_dump())
        service.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            current_user=self.user,
        )
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called(); self.db.delete.assert_not_called()

    def test_nonmember_maps_to_forbidden_without_transaction_writes(self) -> None:
        with patch(
            "app.api.v1.dashboard.dashboard_service.get_dashboard_summary",
            side_effect=DashboardPermissionError("Workspace access denied"),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Workspace access denied"})
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_statistics_serializes_and_remains_read_only(self) -> None:
        statistics = self.statistics()
        with patch(
            "app.api.v1.dashboard.dashboard_statistics_service.get_dashboard_statistics",
            return_value=statistics,
        ) as service:
            response = self.client.get(f"{self.url}/statistics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), statistics.model_dump())
        service.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            current_user=self.user,
        )
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called(); self.db.delete.assert_not_called()

    def test_statistics_nonmember_maps_to_forbidden(self) -> None:
        with patch(
            "app.api.v1.dashboard.dashboard_statistics_service.get_dashboard_statistics",
            side_effect=DashboardStatisticsPermissionError("Workspace access denied"),
        ):
            response = self.client.get(f"{self.url}/statistics")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Workspace access denied"})
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_unauthenticated_and_invalid_workspace_requests_are_rejected(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.assertEqual(self.client.get("/api/v1/workspaces/not-a-uuid/dashboard").status_code, 422)


if __name__ == "__main__":
    unittest.main()
