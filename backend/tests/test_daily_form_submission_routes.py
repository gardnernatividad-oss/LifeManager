import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import DailyFormAnswer, DailyFormAnswerType, DailyFormSubmission, User
from app.services.daily_form_submission_service import (
    DailyFormSubmissionNotFoundError, DailyFormSubmissionPermissionError,
    DailyFormSubmissionValidationError,
)


class DailyFormSubmissionRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.question_id = uuid.uuid4(); self.day = date(2026, 7, 22)
        self.now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/daily-form/submissions/{self.day.isoformat()}"

    def submission(self) -> DailyFormSubmission:
        return DailyFormSubmission(
            id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id,
            definition_id=uuid.uuid4(), submission_date=self.day,
            answers=[DailyFormAnswer(
                question_id=self.question_id, question_title="Done?", question_order=1,
                answer_type=DailyFormAnswerType.BOOLEAN, boolean_value=True,
            )], created_at=self.now, updated_at=self.now,
        )

    def test_put_and_get_serialize_snapshot_with_route_transaction_ownership(self) -> None:
        submission = self.submission()
        with patch("app.api.v1.daily_form.daily_form_submission_service.replace_daily_form_submission", return_value=submission) as replace:
            response = self.client.put(self.url, json={"answers": [{"question_id": str(self.question_id), "value": True}]})
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["answers"][0]["value"], True)
        self.assertEqual(replace.call_args.kwargs["submission_date"], self.day)
        with patch("app.api.v1.daily_form.daily_form_submission_service.get_daily_form_submission", return_value=submission):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["answers"][0]["question_title"], "Done?")
        self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(submission)
        self.db.flush.assert_not_called(); self.db.rollback.assert_not_called()

    def test_body_date_is_forbidden_and_invalid_route_date_is_rejected(self) -> None:
        body = {"submission_date": self.day.isoformat(), "answers": [{"question_id": str(self.question_id), "value": True}]}
        self.assertEqual(self.client.put(self.url, json=body).status_code, 422)
        self.assertEqual(self.client.get(f"/api/v1/workspaces/{self.workspace_id}/daily-form/submissions/22-07-2026").status_code, 422)

    def test_missing_permission_and_validation_errors_map_cleanly(self) -> None:
        with patch("app.api.v1.daily_form.daily_form_submission_service.get_daily_form_submission", side_effect=DailyFormSubmissionNotFoundError("Daily form submission not found")):
            self.assertEqual(self.client.get(self.url).status_code, 404)
        with patch("app.api.v1.daily_form.daily_form_submission_service.get_daily_form_submission", side_effect=DailyFormSubmissionPermissionError("Workspace access denied")):
            self.assertEqual(self.client.get(self.url).status_code, 403)
        with patch("app.api.v1.daily_form.daily_form_submission_service.replace_daily_form_submission", side_effect=DailyFormSubmissionValidationError("Unknown question IDs are not allowed")):
            response = self.client.put(self.url, json={"answers": [{"question_id": str(self.question_id), "value": True}]})
        self.assertEqual(response.status_code, 422); self.assertEqual(response.json()["detail"], "Unknown question IDs are not allowed")
        self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()

    def test_unauthenticated_request_is_rejected(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401); self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")


if __name__ == "__main__":
    unittest.main()
