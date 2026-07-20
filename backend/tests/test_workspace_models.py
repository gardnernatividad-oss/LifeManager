import unittest

from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.dialects.postgresql import UUID

from app.models import User, Workspace, WorkspaceMember


class WorkspaceModelMetadataTests(unittest.TestCase):
    def test_workspace_entities_have_base_entity_columns(self) -> None:
        for model in (Workspace, WorkspaceMember):
            with self.subTest(model=model.__name__):
                columns = model.__table__.columns
                self.assertIsInstance(columns["id"].type, UUID)
                self.assertIn("created_at", columns)
                self.assertIn("updated_at", columns)

    def test_membership_has_unique_user_workspace_constraint(self) -> None:
        unique_column_sets = {
            tuple(column.name for column in constraint.columns)
            for constraint in WorkspaceMember.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }

        self.assertIn(("user_id", "workspace_id"), unique_column_sets)

    def test_membership_foreign_keys_have_explicit_indexes(self) -> None:
        indexed_column_sets = {
            tuple(column.name for column in index.columns)
            for index in WorkspaceMember.__table__.indexes
        }

        self.assertIn(("user_id",), indexed_column_sets)
        self.assertIn(("workspace_id",), indexed_column_sets)

    def test_user_membership_relationship_is_bidirectional(self) -> None:
        user_relationship = inspect(User).relationships["workspace_members"]
        member_relationship = inspect(WorkspaceMember).relationships["user"]

        self.assertEqual(user_relationship.back_populates, "user")
        self.assertEqual(member_relationship.back_populates, "workspace_members")

    def test_workspace_membership_relationship_is_bidirectional(self) -> None:
        workspace_relationship = inspect(Workspace).relationships["members"]
        member_relationship = inspect(WorkspaceMember).relationships["workspace"]

        self.assertEqual(workspace_relationship.back_populates, "workspace")
        self.assertEqual(member_relationship.back_populates, "members")


if __name__ == "__main__":
    unittest.main()
