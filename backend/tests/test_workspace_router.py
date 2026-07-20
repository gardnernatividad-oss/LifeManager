import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.workspaces import get_db
from app.main import app
from app.models import User, Workspace, WorkspaceMember
from app.models.workspace_member import WorkspaceRole


class WorkspaceRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.timestamp = datetime.now(timezone.utc)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def make_workspace(self, *, name: str = "Personal") -> Workspace:
        return Workspace(
            id=uuid.uuid4(),
            name=name,
            description=None,
            created_at=self.timestamp,
            updated_at=self.timestamp,
        )

    def make_membership(
        self,
        workspace: Workspace,
        *,
        user_id: uuid.UUID,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        return WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=role,
        )

    def test_create_workspace_success(self) -> None:
        user_id = uuid.uuid4()
        owner = User(id=user_id)
        workspace = self.make_workspace()
        self.db.get.return_value = owner

        with patch(
            "app.api.v1.workspaces.workspace_service.create_workspace",
            return_value=workspace,
        ) as create_mock:
            response = self.client.post(
                "/api/v1/workspaces",
                params={"user_id": str(user_id)},
                json={"name": "Personal"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], str(workspace.id))
        self.assertEqual(response.json()["name"], "Personal")
        create_mock.assert_called_once()
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(workspace)

    def test_list_workspaces_success(self) -> None:
        user_id = uuid.uuid4()
        workspaces = [self.make_workspace(), self.make_workspace(name="Family")]

        with patch(
            "app.api.v1.workspaces.workspace_service.list_user_workspaces",
            return_value=workspaces,
        ) as list_mock:
            response = self.client.get(
                "/api/v1/workspaces",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(
            [item["name"] for item in response.json()],
            ["Personal", "Family"],
        )
        list_mock.assert_called_once_with(self.db, user_id=user_id)

    def test_get_workspace_not_found(self) -> None:
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch(
            "app.api.v1.workspaces.workspace_service.get_workspace",
            return_value=None,
        ):
            response = self.client.get(
                f"/api/v1/workspaces/{workspace_id}",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Workspace not found"})

    def test_member_can_view_workspace(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()
        membership = self.make_membership(
            workspace,
            user_id=user_id,
            role=WorkspaceRole.MEMBER,
        )

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=membership,
            ),
        ):
            response = self.client.get(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(workspace.id))

    def test_non_member_cannot_view_workspace(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=None,
            ),
        ):
            response = self.client.get(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Workspace access denied"})

    def test_update_workspace_success(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()
        membership = self.make_membership(
            workspace,
            user_id=user_id,
            role=WorkspaceRole.ADMIN,
        )

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=membership,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.update_workspace",
                return_value=workspace,
            ) as update_mock,
        ):
            response = self.client.patch(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
                json={"name": "Updated"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(workspace.id))
        update_mock.assert_called_once()
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(workspace)

    def test_member_cannot_update_workspace(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()
        membership = self.make_membership(
            workspace,
            user_id=user_id,
            role=WorkspaceRole.MEMBER,
        )

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=membership,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.update_workspace"
            ) as update_mock,
        ):
            response = self.client.patch(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
                json={"name": "Updated"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Insufficient workspace permissions"},
        )
        update_mock.assert_not_called()
        self.db.commit.assert_not_called()

    def test_delete_workspace_success(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()
        membership = self.make_membership(
            workspace,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
        )

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=membership,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.delete_workspace"
            ) as delete_mock,
        ):
            response = self.client.delete(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        delete_mock.assert_called_once_with(self.db, workspace=workspace)
        self.db.commit.assert_called_once_with()

    def test_admin_cannot_delete_workspace(self) -> None:
        workspace = self.make_workspace()
        user_id = uuid.uuid4()
        membership = self.make_membership(
            workspace,
            user_id=user_id,
            role=WorkspaceRole.ADMIN,
        )

        with (
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace",
                return_value=workspace,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.get_workspace_membership",
                return_value=membership,
            ),
            patch(
                "app.api.v1.workspaces.workspace_service.delete_workspace"
            ) as delete_mock,
        ):
            response = self.client.delete(
                f"/api/v1/workspaces/{workspace.id}",
                params={"user_id": str(user_id)},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Insufficient workspace permissions"},
        )
        delete_mock.assert_not_called()
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
