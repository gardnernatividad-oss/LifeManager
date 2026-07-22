import unittest
import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import Task, TaskOutcome, User
from app.services.task_resolution_service import (
    TaskAlreadyResolved, TaskNotFound, TaskPermission,
)
from app.services.task_service import (
    TaskNotFoundError, TaskPermissionError,
)


class TaskRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.task_id = uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def collection(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/tasks"

    @property
    def detail(self) -> str:
        return f"{self.collection}/{self.task_id}"

    def task(self, **changes: object) -> Task:
        values = dict(
            id=self.task_id, workspace_id=self.workspace_id, created_by_id=self.user.id,
            category_id=None, project_id=None, title="Task", description=None,
            scheduled_at=self.now - timedelta(hours=1), outcome=None, resolved_at=None,
            created_at=self.now - timedelta(days=1), updated_at=self.now,
        )
        values.update(changes); return Task(**values)

    def test_create_final_payload_commits_and_returns_derived_status(self) -> None:
        task = self.task()
        with patch("app.api.v1.tasks.task_service.create_task", return_value=task) as service:
            response = self.client.post(self.collection, json={"title": "Task", "scheduled_at": self.now.isoformat()})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")
        self.assertNotIn("outcome", response.json())
        for field in ("priority", "due_at", "completed_at", "position", "is_archived"):
            self.assertNotIn(field, response.json())
        self.assertEqual(service.call_args.kwargs["task_in"].scheduled_at, self.now)
        self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(task)

    def test_removed_and_lifecycle_request_fields_are_rejected(self) -> None:
        for field, value in (("status", "pending"), ("outcome", "completed"), ("priority", "high"), ("due_at", self.now.isoformat()), ("is_archived", True), ("resolved_at", self.now.isoformat())):
            with self.subTest(field=field):
                response = self.client.post(self.collection, json={"title": "Task", "scheduled_at": self.now.isoformat(), field: value})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.patch(self.detail, json={"outcome": "cancelled"}).status_code, 422)

    def test_list_uses_filters_one_response_shape_and_no_writes(self) -> None:
        category_id = uuid.uuid4(); project_id = uuid.uuid4()
        task = self.task(category_id=category_id, project_id=project_id, outcome=TaskOutcome.COMPLETED, resolved_at=self.now)
        with patch("app.api.v1.tasks.task_service.list_tasks", return_value=([task], 1)) as service:
            response = self.client.get(f"{self.collection}?category_id={category_id}&project_id={project_id}")
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["status"], "completed")
        service.assert_called_once_with(self.db, workspace_id=self.workspace_id, current_user=self.user, category_id=category_id, project_id=project_id)
        self.db.commit.assert_not_called(); self.db.flush.assert_not_called()

    def test_get_and_update_final_contract(self) -> None:
        task = self.task()
        with patch("app.api.v1.tasks.task_service.get_task", return_value=task):
            self.assertEqual(self.client.get(self.detail).status_code, 200)
        with patch("app.api.v1.tasks.task_service.update_task", return_value=task) as service:
            response = self.client.patch(self.detail, json={"description": None, "scheduled_at": self.now.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.call_args.kwargs["task_in"].model_dump(exclude_unset=True), {"description": None, "scheduled_at": self.now})
        self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(task)

    def test_terminal_endpoints_commit_refresh_and_return_status(self) -> None:
        cases = (
            ("complete", "complete_task", TaskOutcome.COMPLETED, "completed"),
            ("not-complete", "mark_task_not_completed", TaskOutcome.NOT_COMPLETED, "not_completed"),
            ("cancel", "cancel_task", TaskOutcome.CANCELLED, "cancelled"),
        )
        for path, operation, outcome, expected in cases:
            self.db.reset_mock(); task = self.task(outcome=outcome, resolved_at=self.now)
            with self.subTest(path=path), patch(f"app.api.v1.tasks.task_resolution_service.{operation}", return_value=task) as service:
                response = self.client.post(f"{self.detail}/{path}")
            self.assertEqual(response.status_code, 200); self.assertEqual(response.json()["status"], expected)
            service.assert_called_once_with(self.db, workspace_id=self.workspace_id, task_id=self.task_id, current_user=self.user)
            self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(task)

    def test_domain_errors_map_and_write_errors_rollback(self) -> None:
        for error, expected in (
            (TaskNotFoundError("Task not found"), 404),
            (TaskPermissionError("Workspace access denied"), 403),
            (TaskAlreadyResolved("Task is already resolved"), 409),
        ):
            self.db.reset_mock()
            with self.subTest(expected=expected), patch("app.api.v1.tasks.task_service.update_task", side_effect=error):
                response = self.client.patch(self.detail, json={"title": "New"})
            self.assertEqual(response.status_code, expected)
            self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()

    def test_resolution_errors_map_and_rollback(self) -> None:
        for error, expected in (
            (TaskNotFound("Task not found"), 404),
            (TaskPermission("Workspace access denied"), 403),
            (TaskAlreadyResolved("Task is already resolved"), 409),
        ):
            self.db.reset_mock()
            with self.subTest(expected=expected), patch(
                "app.api.v1.tasks.task_resolution_service.complete_task",
                side_effect=error,
            ):
                response = self.client.post(f"{self.detail}/complete")
            self.assertEqual(response.status_code, expected)
            self.db.rollback.assert_called_once(); self.db.commit.assert_not_called()

    def test_auth_uuid_and_no_delete_route(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.collection).status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.assertEqual(self.client.get("/api/v1/workspaces/not-a-uuid/tasks").status_code, 422)
        self.assertEqual(self.client.delete(self.detail).status_code, 405)
        self.assertNotIn("delete", app.openapi()["paths"]["/api/v1/workspaces/{workspace_id}/tasks/{task_id}"])


if __name__ == "__main__":
    unittest.main()
