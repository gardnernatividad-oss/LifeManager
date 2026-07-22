import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import DailyFormAnswerType, DailyFormDefinition, DailyFormQuestion, User
from app.services.daily_form_service import DailyFormNotFoundError, DailyFormPermissionError


class DailyFormRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.now = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/daily-form"

    def definition(self) -> DailyFormDefinition:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id, created_at=self.now, updated_at=self.now)
        definition.questions = [
            DailyFormQuestion(id=uuid.uuid4(), order=1, title="Ready?", description=None, answer_type=DailyFormAnswerType.BOOLEAN, created_at=self.now, updated_at=self.now)
        ]
        return definition

    def test_get_serializes_definition_and_empty_definition_maps_to_404(self) -> None:
        definition = self.definition()
        with patch("app.api.v1.daily_form.daily_form_service.get_daily_form_definition", return_value=definition):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["questions"][0]["answer_type"], "boolean")
        with patch("app.api.v1.daily_form.daily_form_service.get_daily_form_definition", side_effect=DailyFormNotFoundError("Daily form definition not found")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_put_replaces_all_questions_commits_refreshes_and_serializes_order(self) -> None:
        definition = self.definition()
        with patch("app.api.v1.daily_form.daily_form_service.replace_daily_form_definition", return_value=definition) as service:
            response = self.client.put(self.url, json={"questions": [{"order": 1, "title": "Ready?", "answer_type": "boolean"}]})
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["questions"][0]["order"], 1)
        self.assertEqual(service.call_args.kwargs["definition_in"].questions[0].title, "Ready?")
        self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(definition); self.db.rollback.assert_not_called()

    def test_validation_and_authorization_errors(self) -> None:
        for payload in ({"questions": []}, {"questions": [{"order": 1, "title": "", "answer_type": "boolean"}]}, {"questions": [{"order": 1, "title": "Q", "answer_type": "invalid"}]}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.put(self.url, json=payload).status_code, 422)
        with patch("app.api.v1.daily_form.daily_form_service.get_daily_form_definition", side_effect=DailyFormPermissionError("Workspace access denied")):
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.db.commit.assert_not_called()

    def test_put_permission_error_rolls_back_and_unauthenticated_is_rejected(self) -> None:
        with patch("app.api.v1.daily_form.daily_form_service.replace_daily_form_definition", side_effect=DailyFormPermissionError("Workspace access denied")):
            response = self.client.put(self.url, json={"questions": [{"order": 1, "title": "Q", "answer_type": "text"}]})
        self.assertEqual(response.status_code, 403); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.url).status_code, 401)


if __name__ == "__main__":
    unittest.main()
