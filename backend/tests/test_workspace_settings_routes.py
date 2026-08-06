import unittest
import uuid

from datetime import datetime, time, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User, WeekStartsOn, WorkspaceSettings
from app.services.workspace_settings_service import WorkspaceSettingsPermissionError, WorkspaceSettingsValidationError


class WorkspaceSettingsRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.user = User(id=uuid.uuid4(), is_active=True); self.workspace_id = uuid.uuid4(); self.now = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db; app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app); self.url = f"/api/v1/workspaces/{self.workspace_id}/settings"

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    def settings(self) -> WorkspaceSettings:
        return WorkspaceSettings(id=uuid.uuid4(), workspace_id=self.workspace_id, timezone="America/Lima",
            daily_form_enabled=True, daily_form_reminder_time=time(9), daily_task_generation_enabled=True,
            week_starts_on=WeekStartsOn.MONDAY, created_at=self.now, updated_at=self.now)

    @staticmethod
    def payload() -> dict[str, object]:
        return {"timezone": "UTC", "daily_form_enabled": False, "daily_form_reminder_time": "10:00:00",
                "daily_task_generation_enabled": True, "week_starts_on": "SUNDAY"}

    def test_get_and_put_commit_refresh_serialize_and_use_route_workspace(self) -> None:
        for method, operation in (("get", "get_or_create_workspace_settings"), ("put", "replace_workspace_settings")):
            self.db.reset_mock(); settings = self.settings()
            with self.subTest(method=method), patch(f"app.api.v1.workspace_settings.workspace_settings_service.{operation}", return_value=settings) as service:
                response = self.client.get(self.url) if method == "get" else self.client.put(self.url, json=self.payload())
            self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["workspace_id"], str(self.workspace_id))
            self.assertEqual(service.call_args.kwargs["workspace_id"], self.workspace_id); self.assertIs(service.call_args.kwargs["current_user"], self.user)
            self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(settings); self.db.rollback.assert_not_called()

    def test_schema_domain_auth_and_unexpected_errors(self) -> None:
        for changes in ({"workspace_id": str(uuid.uuid4())}, {"timezone": "Bad/Zone"}, {"week_starts_on": "BAD"}):
            payload = self.payload(); payload.update(changes); self.assertEqual(self.client.put(self.url, json=payload).status_code, 422)
        for error, expected in ((WorkspaceSettingsPermissionError("denied"), 403), (WorkspaceSettingsValidationError("invalid"), 422)):
            self.db.reset_mock()
            with patch("app.api.v1.workspace_settings.workspace_settings_service.replace_workspace_settings", side_effect=error): response = self.client.put(self.url, json=self.payload())
            self.assertEqual(response.status_code, expected); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()
        app.dependency_overrides.pop(get_current_user); self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_unexpected_failure_rolls_back(self) -> None:
        with patch("app.api.v1.workspace_settings.workspace_settings_service.get_or_create_workspace_settings", side_effect=RuntimeError("failure")), TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(self.url)
        self.assertEqual(response.status_code, 500); self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()


if __name__ == "__main__": unittest.main()
