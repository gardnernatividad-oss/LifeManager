import unittest
import uuid

from datetime import datetime, time, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User, UserSettings, WeekStartsOn
from app.services.user_settings_service import UserSettingsValidationError


class UserSettingsRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True); self.now = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db; app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app); self.url = "/api/v1/users/me/settings"

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    def settings(self) -> UserSettings:
        return UserSettings(
            id=uuid.uuid4(), user_id=self.user.id, timezone="America/Lima", locale="es-PE",
            week_starts_on=WeekStartsOn.MONDAY, daily_form_reminders_enabled=True,
            task_due_reminders_enabled=True, task_overdue_reminders_enabled=True,
            daily_form_reminder_time=time(9), task_due_reminder_minutes=60,
            created_at=self.now, updated_at=self.now,
        )

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "timezone": "UTC", "locale": "en-US", "week_starts_on": "SUNDAY",
            "daily_form_reminders_enabled": False, "task_due_reminders_enabled": True,
            "task_overdue_reminders_enabled": False, "daily_form_reminder_time": "10:15:00",
            "task_due_reminder_minutes": 0,
        }

    def test_get_and_put_use_current_user_commit_refresh_and_serialize(self) -> None:
        for method, service_path in (("get", "get_or_create_user_settings"), ("put", "replace_user_settings")):
            self.db.reset_mock(); settings = self.settings()
            with self.subTest(method=method), patch(f"app.api.v1.user_settings.user_settings_service.{service_path}", return_value=settings) as service:
                response = self.client.get(self.url) if method == "get" else self.client.put(self.url, json=self.payload())
            self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["user_id"], str(self.user.id))
            self.assertIs(service.call_args.kwargs["current_user"], self.user)
            self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(settings); self.db.rollback.assert_not_called()

    def test_validation_protected_fields_auth_and_error_rollback(self) -> None:
        for changes in ({"user_id": str(uuid.uuid4())}, {"timezone": "Bad/Zone"}, {"locale": " "}, {"week_starts_on": "BAD"}):
            payload = self.payload(); payload.update(changes)
            self.assertEqual(self.client.put(self.url, json=payload).status_code, 422)
        with patch("app.api.v1.user_settings.user_settings_service.replace_user_settings", side_effect=UserSettingsValidationError("invalid")):
            response = self.client.put(self.url, json=self.payload())
        self.assertEqual(response.status_code, 422); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_unexpected_error_rolls_back(self) -> None:
        with patch("app.api.v1.user_settings.user_settings_service.get_or_create_user_settings", side_effect=RuntimeError("failure")), TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(self.url)
        self.assertEqual(response.status_code, 500); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
