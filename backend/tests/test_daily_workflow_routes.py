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
from app.schemas.daily_workflow import DailyWorkflowResponse, DailyWorkflowStatus
from app.services.task_materialization_service import TaskMaterializationConflictError
from app.services.task_series_service import TaskSeriesPermissionError


class DailyWorkflowRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.day = date(2026, 7, 22); self.now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db; app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/daily-workflow/{self.day.isoformat()}"

    def response(self) -> DailyWorkflowResponse:
        generation = DailyTaskGenerationResponse(
            workspace_id=self.workspace_id, generation_date=self.day, eligible_series_count=0,
            created_task_count=0, skipped_existing_count=0, created_task_ids=[], generated_at=self.now,
        )
        return DailyWorkflowResponse(
            workspace_id=self.workspace_id, user_id=self.user.id, workflow_date=self.day,
            workflow_status=DailyWorkflowStatus.READY, form_required=False, form_submitted=False,
            definition_id=None, submission_id=None, task_generation=generation, evaluated_at=self.now,
        )

    def test_success_serializes_embedded_generation_and_commits_once(self) -> None:
        result = self.response()
        with patch("app.api.v1.daily_workflow.daily_workflow_service.initialize_daily_workflow", return_value=result) as service:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json(), result.model_dump(mode="json"))
        self.assertEqual(response.json()["workflow_status"], "READY")
        service.assert_called_once_with(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        self.db.commit.assert_called_once(); self.db.rollback.assert_not_called(); self.db.refresh.assert_not_called()

    def test_permission_materialization_and_unexpected_errors_rollback(self) -> None:
        cases = (
            (TaskSeriesPermissionError("Workspace access denied"), 403),
            (TaskMaterializationConflictError("concurrent"), 409),
            (RuntimeError("failure"), 500),
        )
        for error, expected in cases:
            self.db.reset_mock()
            with self.subTest(expected=expected), patch("app.api.v1.daily_workflow.daily_workflow_service.initialize_daily_workflow", side_effect=error), TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(self.url)
            self.assertEqual(response.status_code, expected); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()

    def test_route_date_is_authoritative_and_invalid_date_is_rejected(self) -> None:
        result = self.response()
        with patch("app.api.v1.daily_workflow.daily_workflow_service.initialize_daily_workflow", return_value=result) as service:
            self.client.post(self.url)
        self.assertEqual(service.call_args.kwargs["workflow_date"], self.day)
        invalid = f"/api/v1/workspaces/{self.workspace_id}/daily-workflow/22-07-2026"
        self.assertEqual(self.client.post(invalid).status_code, 422)


if __name__ == "__main__":
    unittest.main()
