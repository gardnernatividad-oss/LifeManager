import unittest
import uuid

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas import WorkspaceCreate, WorkspaceUpdate
from app.services.workspace import (
    create_workspace,
    delete_workspace,
    get_workspace,
    list_user_workspaces,
    update_workspace,
)


class WorkspaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)

    def test_create_workspace_adds_workspace_and_owner_membership(self) -> None:
        owner = User(id=uuid.uuid4())

        workspace = create_workspace(
            self.db,
            owner=owner,
            workspace_in=WorkspaceCreate(name="Personal"),
        )

        added_objects = [call.args[0] for call in self.db.add.call_args_list]
        self.assertIs(added_objects[0], workspace)
        self.assertIsInstance(added_objects[1], WorkspaceMember)
        self.assertIs(added_objects[1].user, owner)
        self.assertIs(added_objects[1].workspace, workspace)
        self.assertIs(added_objects[1].role, WorkspaceRole.OWNER)
        self.db.commit.assert_not_called()

    def test_create_workspace_flushes_before_constructing_membership(self) -> None:
        owner = User(id=uuid.uuid4())

        def build_membership(**kwargs: object) -> WorkspaceMember:
            self.db.flush.assert_called_once_with()
            return WorkspaceMember(**kwargs)

        with patch(
            "app.services.workspace.WorkspaceMember",
            side_effect=build_membership,
        ):
            create_workspace(
                self.db,
                owner=owner,
                workspace_in=WorkspaceCreate(name="Personal"),
            )

        self.assertEqual(self.db.method_calls[0][0], "add")
        self.assertEqual(self.db.method_calls[1][0], "flush")
        self.assertEqual(self.db.method_calls[2][0], "add")

    def test_get_workspace_uses_requested_uuid(self) -> None:
        workspace_id = uuid.uuid4()
        expected = Workspace(name="Personal")
        self.db.scalar.return_value = expected

        result = get_workspace(self.db, workspace_id=workspace_id)

        statement = self.db.scalar.call_args.args[0]
        self.assertIn(workspace_id, statement.compile().params.values())
        self.assertIs(result, expected)

    def test_list_user_workspaces_joins_memberships_and_returns_scalars(self) -> None:
        user_id = uuid.uuid4()
        expected = [Workspace(name="Personal"), Workspace(name="Family")]
        self.db.scalars.return_value.all.return_value = expected

        result = list_user_workspaces(self.db, user_id=user_id)

        statement = self.db.scalars.call_args.args[0]
        sql = str(statement)
        self.assertIn("JOIN workspace_members", sql)
        self.assertIn(user_id, statement.compile().params.values())
        self.assertIn("DISTINCT", sql)
        self.assertIn("ORDER BY workspaces.created_at, workspaces.id", sql)
        self.assertEqual(result, expected)

    def test_update_workspace_changes_only_explicit_fields(self) -> None:
        workspace = Workspace(name="Personal", description="Original")

        result = update_workspace(
            self.db,
            workspace=workspace,
            workspace_in=WorkspaceUpdate(description=None),
        )

        self.assertIs(result, workspace)
        self.assertEqual(workspace.name, "Personal")
        self.assertIsNone(workspace.description)
        self.db.flush.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_delete_workspace_deletes_and_flushes_without_commit(self) -> None:
        workspace = Workspace(name="Personal")

        result = delete_workspace(self.db, workspace=workspace)

        self.assertIsNone(result)
        self.db.delete.assert_called_once_with(workspace)
        self.db.flush.assert_called_once_with()
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
