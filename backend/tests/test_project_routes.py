import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import Project, User
from app.services.project_service import ProjectNameConflictError, ProjectNotFoundError, ProjectPermissionError


class ProjectRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user = User(id=uuid.uuid4(), is_active=True)
        self.workspace_id = uuid.uuid4(); self.project_id = uuid.uuid4()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); app.dependency_overrides.clear()

    @property
    def collection(self) -> str:
        return f"/api/v1/workspaces/{self.workspace_id}/projects"

    @property
    def detail(self) -> str:
        return f"{self.collection}/{self.project_id}"

    def project(self, **changes: object) -> Project:
        now = datetime.now(timezone.utc)
        values = dict(id=self.project_id, workspace_id=self.workspace_id, name="Personal", normalized_name="personal", description=None, is_active=True, created_at=now, updated_at=now)
        values.update(changes); return Project(**values)

    def test_create_commits_refreshes_and_hides_internal_name(self) -> None:
        project = self.project()
        with patch("app.api.v1.projects.project_service.create_project", return_value=project):
            response = self.client.post(self.collection, json={"name": "Personal"})
        self.assertEqual(response.status_code, 201); self.assertNotIn("normalized_name", response.json())
        self.db.commit.assert_called_once(); self.db.refresh.assert_called_once_with(project)

    def test_auth_permission_conflict_missing_and_rollback(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.collection).status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: self.user
        cases = (
            ("list_projects", ProjectPermissionError("Workspace access denied"), 403, "get", self.collection),
            ("get_project", ProjectNotFoundError("Project not found"), 404, "get", self.detail),
            ("create_project", ProjectNameConflictError("Project name already exists"), 409, "post", self.collection),
        )
        for method, error, status, verb, url in cases:
            self.db.reset_mock()
            with self.subTest(status=status), patch(f"app.api.v1.projects.project_service.{method}", side_effect=error):
                if verb == "post":
                    response = self.client.post(url, json={"name": "X"})
                else:
                    response = self.client.get(url)
            self.assertEqual(response.status_code, status)
            if verb == "post": self.db.rollback.assert_called_once()

    def test_list_filters_get_update_and_lifecycle(self) -> None:
        projects = [self.project()]
        for query, active in (("", None), ("?active=true", True), ("?active=false", False)):
            with patch("app.api.v1.projects.project_service.list_projects", return_value=projects) as mocked:
                response = self.client.get(self.collection + query)
            self.assertEqual(response.status_code, 200)
            mocked.assert_called_once_with(self.db, workspace_id=self.workspace_id, current_user=self.user, active=active)
        with patch("app.api.v1.projects.project_service.get_project", return_value=projects[0]):
            self.assertEqual(self.client.get(self.detail).status_code, 200)
        with patch("app.api.v1.projects.project_service.update_project", return_value=projects[0]) as mocked:
            response = self.client.patch(self.detail, json={"description": None})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked.call_args.kwargs["project_in"].model_dump(exclude_unset=True), {"description": None})
        for action, active in (("deactivate", False), ("activate", True)):
            self.db.reset_mock(); project = self.project(is_active=active)
            with patch(f"app.api.v1.projects.project_service.{action}_project", return_value=project):
                response = self.client.post(f"{self.detail}/{action}")
            self.assertEqual(response.status_code, 200); self.db.commit.assert_called_once()

    def test_protected_fields_and_delete_are_rejected_and_openapi_has_no_delete(self) -> None:
        for field, value in (("workspace_id", str(uuid.uuid4())), ("normalized_name", "x"), ("is_active", False), ("id", str(uuid.uuid4()))):
            response = self.client.post(self.collection, json={"name": "X", field: value})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.delete(self.detail).status_code, 405)
        self.assertNotIn("delete", app.openapi()["paths"]["/api/v1/workspaces/{workspace_id}/projects/{project_id}"])


if __name__ == "__main__":
    unittest.main()
