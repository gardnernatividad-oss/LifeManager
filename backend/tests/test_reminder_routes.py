import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User
from app.schemas.reminder import ReminderEvaluationResponse, ReminderItem, ReminderType
from app.services.reminder_service import ReminderPermissionError, ReminderTimezoneError


class ReminderRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True); self.workspace_id = uuid.uuid4()
        self.evaluated = datetime(2026, 7, 22, 14, tzinfo=timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db; app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/reminders"

    def response(self) -> ReminderEvaluationResponse:
        task_id = uuid.uuid4()
        item = ReminderItem(
            reminder_type=ReminderType.TASK_DUE, entity_id=task_id, title="Task",
            scheduled_for=self.evaluated, local_date=date(2026, 7, 22),
            metadata={"task_id": str(task_id), "minutes_until_due": 0},
        )
        return ReminderEvaluationResponse(
            workspace_id=self.workspace_id, user_id=self.user.id, evaluated_at=self.evaluated,
            local_date=date(2026, 7, 22), timezone="America/Lima", reminder_count=1, reminders=[item],
        )

    def test_timezone_aware_request_serializes_and_is_read_only(self) -> None:
        result = self.response()
        with patch("app.api.v1.reminders.reminder_service.evaluate_reminders", return_value=result) as service:
            response = self.client.get(self.url, params={"evaluated_at": self.evaluated.isoformat()})
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json(), result.model_dump(mode="json"))
        service.assert_called_once_with(self.db, workspace_id=self.workspace_id, current_user=self.user, evaluated_at=self.evaluated)
        self.db.add.assert_not_called(); self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.refresh.assert_not_called(); self.db.rollback.assert_not_called()

    def test_missing_naive_and_invalid_datetime_are_rejected(self) -> None:
        for params in ({}, {"evaluated_at": "2026-07-22T14:00:00"}, {"evaluated_at": "invalid"}):
            with self.subTest(params=params), patch("app.api.v1.reminders.reminder_service.evaluate_reminders") as service:
                response = self.client.get(self.url, params=params)
            self.assertEqual(response.status_code, 422); service.assert_not_called()

    def test_domain_errors_map_without_success_commit(self) -> None:
        for error, expected in ((ReminderPermissionError("Workspace access denied"), 403), (ReminderTimezoneError("Workspace timezone is invalid"), 409)):
            self.db.reset_mock()
            with self.subTest(expected=expected), patch("app.api.v1.reminders.reminder_service.evaluate_reminders", side_effect=error):
                response = self.client.get(self.url, params={"evaluated_at": self.evaluated.isoformat()})
            self.assertEqual(response.status_code, expected); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_unexpected_failure_rolls_back(self) -> None:
        with patch("app.api.v1.reminders.reminder_service.evaluate_reminders", side_effect=RuntimeError("failure")), TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(self.url, params={"evaluated_at": self.evaluated.isoformat()})
        self.assertEqual(response.status_code, 500); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
