import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import Task, TaskPriority, TaskStatus, User
from app.services.task_service import (
    TaskCategoryInactiveError,
    TaskCategoryNotFoundError,
    TaskNotFoundError,
    TaskPermissionError,
)


class TaskRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4()
        self.task_id = uuid.uuid4()
        self.timestamp = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    @property
    def collection_url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/tasks"

    @property
    def detail_url(self) -> str:
        return f"{self.collection_url}/{self.task_id}"

    def make_task(
        self,
        *,
        title: str = "Task",
        category_id: uuid.UUID | None = None,
    ) -> Task:
        return Task(
            id=self.task_id,
            workspace_id=self.workspace_id,
            created_by_id=self.user.id,
            category_id=category_id,
            title=title,
            description=None,
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            due_at=None,
            completed_at=None,
            position=0,
            is_archived=False,
            created_at=self.timestamp,
            updated_at=self.timestamp,
        )

    def assert_read_session(self) -> None:
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.delete.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.rollback.assert_not_called()

    def test_create_returns_201_and_uses_path_and_current_user(self) -> None:
        task = self.make_task()
        with patch(
            "app.api.v1.tasks.task_service.create_task",
            return_value=task,
        ) as service_mock:
            response = self.client.post(self.collection_url, json={"title": "Task"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], str(task.id))
        self.assertIsNone(response.json()["category_id"])
        call = service_mock.call_args
        self.assertEqual(call.kwargs["workspace_id"], self.workspace_id)
        self.assertIs(call.kwargs["current_user"], self.user)
        self.assertNotIn("workspace_id", call.kwargs["task_in"].model_dump())
        self.assertNotIn("created_by_id", call.kwargs["task_in"].model_dump())
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(task)

    def test_create_with_category_passes_id_and_serializes_it(self) -> None:
        category_id = uuid.uuid4()
        task = self.make_task(category_id=category_id)
        with patch(
            "app.api.v1.tasks.task_service.create_task",
            return_value=task,
        ) as service_mock:
            response = self.client.post(
                self.collection_url,
                json={"title": "Task", "category_id": str(category_id)},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["category_id"], str(category_id))
        self.assertEqual(
            service_mock.call_args.kwargs["task_in"].category_id,
            category_id,
        )

    def test_create_rejects_protected_fields_and_maps_permission_error(self) -> None:
        invalid = self.client.post(
            self.collection_url,
            json={"title": "Task", "workspace_id": str(uuid.uuid4())},
        )
        self.assertEqual(invalid.status_code, 422)

        with patch(
            "app.api.v1.tasks.task_service.create_task",
            side_effect=TaskPermissionError("Workspace access denied"),
        ):
            denied = self.client.post(self.collection_url, json={"title": "Task"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json(), {"detail": "Workspace access denied"})
        self.db.rollback.assert_called_once_with()

    def test_list_returns_items_total_and_does_not_write(self) -> None:
        task = self.make_task()
        with patch(
            "app.api.v1.tasks.task_service.list_tasks",
            return_value=([task], 1),
        ) as service_mock:
            response = self.client.get(self.collection_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], str(task.id))
        service_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            current_user=self.user,
            category_id=None,
        )
        self.assert_read_session()

    def test_list_filters_by_category_id(self) -> None:
        category_id = uuid.uuid4()
        task = self.make_task(category_id=category_id)
        with patch(
            "app.api.v1.tasks.task_service.list_tasks",
            return_value=([task], 1),
        ) as service_mock:
            response = self.client.get(
                f"{self.collection_url}?category_id={category_id}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["category_id"], str(category_id))
        service_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            current_user=self.user,
            category_id=category_id,
        )

    def test_list_permission_error_maps_to_403(self) -> None:
        with patch(
            "app.api.v1.tasks.task_service.list_tasks",
            side_effect=TaskPermissionError("Workspace access denied"),
        ):
            response = self.client.get(self.collection_url)
        self.assertEqual(response.status_code, 403)
        self.assert_read_session()

    def test_get_passes_scoped_ids_and_maps_errors(self) -> None:
        task = self.make_task()
        with patch(
            "app.api.v1.tasks.task_service.get_task",
            return_value=task,
        ) as service_mock:
            response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        service_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            task_id=self.task_id,
            current_user=self.user,
        )
        self.assert_read_session()

        for error, expected_status in (
            (TaskNotFoundError("Task not found"), 404),
            (TaskPermissionError("Workspace access denied"), 403),
        ):
            with self.subTest(status=expected_status), patch(
                "app.api.v1.tasks.task_service.get_task",
                side_effect=error,
            ):
                error_response = self.client.get(self.detail_url)
            self.assertEqual(error_response.status_code, expected_status)

    def test_update_preserves_explicit_nulls_and_commits(self) -> None:
        task = self.make_task(title="Updated")
        with patch(
            "app.api.v1.tasks.task_service.update_task",
            return_value=task,
        ) as service_mock:
            response = self.client.patch(
                self.detail_url,
                json={"title": "Updated", "description": None, "due_at": None},
            )

        self.assertEqual(response.status_code, 200)
        task_in = service_mock.call_args.kwargs["task_in"]
        self.assertEqual(
            task_in.model_dump(exclude_unset=True),
            {"title": "Updated", "description": None, "due_at": None},
        )
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(task)

    def test_update_assigns_and_clears_category_id(self) -> None:
        category_id = uuid.uuid4()
        for payload, response_category_id in (
            ({"category_id": str(category_id)}, category_id),
            ({"category_id": None}, None),
        ):
            self.db.reset_mock()
            task = self.make_task(category_id=response_category_id)
            with self.subTest(payload=payload), patch(
                "app.api.v1.tasks.task_service.update_task",
                return_value=task,
            ) as service_mock:
                response = self.client.patch(self.detail_url, json=payload)

            self.assertEqual(response.status_code, 200)
            expected = (
                str(response_category_id)
                if response_category_id is not None
                else None
            )
            self.assertEqual(response.json()["category_id"], expected)
            self.assertEqual(
                service_mock.call_args.kwargs["task_in"].model_dump(
                    exclude_unset=True
                ),
                {"category_id": response_category_id},
            )

    def test_category_assignment_errors_map_to_404_and_409(self) -> None:
        category_id = uuid.uuid4()
        for error, expected_status, detail in (
            (TaskCategoryNotFoundError("Category not found"), 404, "Category not found"),
            (TaskCategoryInactiveError("Category is inactive"), 409, "Category is inactive"),
        ):
            self.db.reset_mock()
            with self.subTest(status=expected_status), patch(
                "app.api.v1.tasks.task_service.create_task",
                side_effect=error,
            ):
                response = self.client.post(
                    self.collection_url,
                    json={"title": "Task", "category_id": str(category_id)},
                )
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json(), {"detail": detail})
            self.db.rollback.assert_called_once_with()

    def test_update_maps_not_found_and_permission_errors(self) -> None:
        for error, expected_status in (
            (TaskNotFoundError("Task not found"), 404),
            (TaskPermissionError("Insufficient task permissions"), 403),
        ):
            self.db.reset_mock()
            with self.subTest(status=expected_status), patch(
                "app.api.v1.tasks.task_service.update_task",
                side_effect=error,
            ):
                response = self.client.patch(self.detail_url, json={"title": "New"})
            self.assertEqual(response.status_code, expected_status)
            self.db.rollback.assert_called_once_with()
            self.db.commit.assert_not_called()

    def test_delete_returns_empty_204_and_delegates_policy(self) -> None:
        with patch("app.api.v1.tasks.task_service.delete_task") as service_mock:
            response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        service_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            task_id=self.task_id,
            current_user=self.user,
        )
        self.db.commit.assert_called_once_with()

    def test_delete_maps_not_found_and_permission_errors(self) -> None:
        for error, expected_status in (
            (TaskNotFoundError("Task not found"), 404),
            (TaskPermissionError("Insufficient task permissions"), 403),
        ):
            self.db.reset_mock()
            with self.subTest(status=expected_status), patch(
                "app.api.v1.tasks.task_service.delete_task",
                side_effect=error,
            ):
                response = self.client.delete(self.detail_url)
            self.assertEqual(response.status_code, expected_status)
            self.db.rollback.assert_called_once_with()
            self.db.commit.assert_not_called()

    def test_auth_uuid_validation_unknown_fields_and_no_user_id(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.collection_url).status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: self.user

        self.assertEqual(
            self.client.get("/api/v1/workspaces/not-a-uuid/tasks").status_code,
            422,
        )
        self.assertEqual(
            self.client.get(f"{self.collection_url}/not-a-uuid").status_code,
            422,
        )
        self.assertEqual(
            self.client.get(
                f"{self.collection_url}?category_id=not-a-uuid"
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.patch(self.detail_url, json={"unknown": True}).status_code,
            422,
        )
        schema = app.openapi()
        for path, operations in schema["paths"].items():
            if "/tasks" not in path:
                continue
            for operation in operations.values():
                names = {item["name"] for item in operation.get("parameters", [])}
                self.assertNotIn("user_id", names)


if __name__ == "__main__":
    unittest.main()
