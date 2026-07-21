import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import Category, User
from app.services.category_service import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    CategoryPermissionError,
)


class CategoryRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4()
        self.category_id = uuid.uuid4()
        self.timestamp = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    @property
    def collection_url(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/categories"

    @property
    def detail_url(self) -> str:
        return f"{self.collection_url}/{self.category_id}"

    def make_category(self, **overrides: object) -> Category:
        values: dict[str, object] = {
            "id": self.category_id,
            "workspace_id": self.workspace_id,
            "name": "Trabajo",
            "normalized_name": "trabajo",
            "description": None,
            "is_active": True,
            "created_at": self.timestamp,
            "updated_at": self.timestamp,
        }
        values.update(overrides)
        return Category(**values)

    def test_authenticated_create_commits_and_hides_normalized_name(self) -> None:
        category = self.make_category()
        with patch(
            "app.api.v1.categories.category_service.create_category",
            return_value=category,
        ) as service_mock:
            response = self.client.post(
                self.collection_url,
                json={"name": "Trabajo"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("normalized_name", response.json())
        self.assertEqual(response.json()["name"], "Trabajo")
        service_mock.assert_called_once()
        self.assertEqual(service_mock.call_args.kwargs["workspace_id"], self.workspace_id)
        self.assertIs(service_mock.call_args.kwargs["current_user"], self.user)
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(category)

    def test_unauthenticated_request_is_rejected(self) -> None:
        app.dependency_overrides.pop(get_current_user)

        response = self.client.get(self.collection_url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_nonmember_permission_error_maps_to_403(self) -> None:
        with patch(
            "app.api.v1.categories.category_service.list_categories",
            side_effect=CategoryPermissionError("Workspace access denied"),
        ):
            response = self.client.get(self.collection_url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Workspace access denied"})

    def test_list_all_and_active_filters(self) -> None:
        categories = [self.make_category(), self.make_category(id=uuid.uuid4())]
        for query, expected_active in (("", None), ("?active=true", True), ("?active=false", False)):
            with self.subTest(query=query), patch(
                "app.api.v1.categories.category_service.list_categories",
                return_value=categories,
            ) as service_mock:
                response = self.client.get(f"{self.collection_url}{query}")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 2)
            service_mock.assert_called_once_with(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
                active=expected_active,
            )

    def test_get_is_workspace_scoped_and_missing_maps_to_404(self) -> None:
        category = self.make_category(is_active=False)
        with patch(
            "app.api.v1.categories.category_service.get_category",
            return_value=category,
        ) as service_mock:
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        service_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            category_id=self.category_id,
            current_user=self.user,
        )

        with patch(
            "app.api.v1.categories.category_service.get_category",
            side_effect=CategoryNotFoundError("Category not found"),
        ):
            missing = self.client.get(self.detail_url)
        self.assertEqual(missing.status_code, 404)

    def test_update_commits_and_passes_partial_payload(self) -> None:
        category = self.make_category(description="Updated")
        with patch(
            "app.api.v1.categories.category_service.update_category",
            return_value=category,
        ) as service_mock:
            response = self.client.patch(
                self.detail_url,
                json={"description": "Updated"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            service_mock.call_args.kwargs["category_in"].model_dump(exclude_unset=True),
            {"description": "Updated"},
        )
        self.db.commit.assert_called_once_with()

    def test_activate_and_deactivate_commit(self) -> None:
        for action, active in (("activate", True), ("deactivate", False)):
            self.db.reset_mock()
            category = self.make_category(is_active=active)
            with self.subTest(action=action), patch(
                f"app.api.v1.categories.category_service.{action}_category",
                return_value=category,
            ) as service_mock:
                response = self.client.post(f"{self.detail_url}/{action}")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["is_active"], active)
            service_mock.assert_called_once_with(
                self.db,
                workspace_id=self.workspace_id,
                category_id=self.category_id,
                current_user=self.user,
            )
            self.db.commit.assert_called_once_with()

    def test_duplicate_name_maps_to_409_and_rolls_back(self) -> None:
        with patch(
            "app.api.v1.categories.category_service.create_category",
            side_effect=CategoryNameConflictError("Category name already exists"),
        ):
            response = self.client.post(
                self.collection_url,
                json={"name": "Trabajo"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"detail": "Category name already exists"},
        )
        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_write_not_found_and_access_denial_are_mapped(self) -> None:
        for error, expected_status in (
            (CategoryNotFoundError("Category not found"), 404),
            (CategoryPermissionError("Workspace access denied"), 403),
        ):
            self.db.reset_mock()
            with self.subTest(status=expected_status), patch(
                "app.api.v1.categories.category_service.update_category",
                side_effect=error,
            ):
                response = self.client.patch(self.detail_url, json={"name": "New"})
            self.assertEqual(response.status_code, expected_status)
            self.db.rollback.assert_called_once_with()

    def test_no_delete_route_and_requests_reject_protected_fields(self) -> None:
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 405)

        for payload in (
            {"name": "Test", "workspace_id": str(uuid.uuid4())},
            {"name": "Test", "normalized_name": "test"},
            {"name": "Test", "is_active": False},
        ):
            with self.subTest(payload=payload):
                rejected = self.client.post(self.collection_url, json=payload)
            self.assertEqual(rejected.status_code, 422)

        schema = app.openapi()
        self.assertNotIn(
            "delete",
            schema["paths"][
                "/api/v1/workspaces/{workspace_id}/categories/{category_id}"
            ],
        )


if __name__ == "__main__":
    unittest.main()
