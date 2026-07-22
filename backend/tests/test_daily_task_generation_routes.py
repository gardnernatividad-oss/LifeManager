import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.services.task_series_service import TaskSeriesPermissionError


class DailyTaskGenerationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.day = date(2026, 7, 22)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/daily-task-generation/{self.day.isoformat()}"

    def result(self) -> DailyTaskGenerationResponse:
        return DailyTaskGenerationResponse(
            workspace_id=self.workspace_id, generation_date=self.day,
            eligible_series_count=2, created_task_count=1, skipped_existing_count=1,
            created_task_ids=[uuid.uuid4()], generated_at=datetime(2026, 7, 22, 12, tzinfo=timezone.utc),
        )

    def test_success_serializes_and_commits_once(self) -> None:
        result = self.result()
        with patch("app.api.v1.daily_task_generation.daily_task_generation_service.generate_daily_tasks", return_value=result) as service:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json(), result.model_dump(mode="json"))
        service.assert_called_once_with(self.db, workspace_id=self.workspace_id, generation_date=self.day, current_user=self.user)
        self.db.commit.assert_called_once(); self.db.rollback.assert_not_called(); self.db.refresh.assert_not_called()

    def test_domain_and_unexpected_failures_rollback(self) -> None:
        for error, expected in ((TaskSeriesPermissionError("Workspace access denied"), 403), (RuntimeError("failure"), 500)):
            self.db.reset_mock()
            with self.subTest(expected=expected), patch("app.api.v1.daily_task_generation.daily_task_generation_service.generate_daily_tasks", side_effect=error), TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(self.url)
            self.assertEqual(response.status_code, expected); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()

    def test_invalid_date_and_unauthenticated_requests_are_rejected(self) -> None:
        invalid = f"/api/v1/workspaces/{self.workspace_id}/daily-task-generation/22-07-2026"
        self.assertEqual(self.client.post(invalid).status_code, 422)
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.post(self.url).status_code, 401)


if __name__ == "__main__":
    unittest.main()
