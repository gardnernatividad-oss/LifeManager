import unittest

from sqlalchemy import CheckConstraint, UniqueConstraint, inspect

from app.models import Category, Workspace
from app.models.base import Base


class CategoryModelTests(unittest.TestCase):
    def test_fields_defaults_and_registration(self) -> None:
        columns = Category.__table__.columns

        self.assertEqual(columns["name"].type.length, 100)
        self.assertEqual(columns["normalized_name"].type.length, 100)
        self.assertEqual(columns["description"].type.length, 500)
        self.assertFalse(columns["workspace_id"].nullable)
        self.assertFalse(columns["is_active"].nullable)
        self.assertIs(columns["is_active"].default.arg, True)
        self.assertEqual(str(columns["is_active"].server_default.arg), "true")
        self.assertIs(Base.metadata.tables["categories"], Category.__table__)

    def test_constraints_and_listing_index(self) -> None:
        unique_constraints = {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in Category.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        check_names = {
            constraint.name
            for constraint in Category.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        indexes = {
            (index.name, tuple(column.name for column in index.columns))
            for index in Category.__table__.indexes
        }

        self.assertIn(
            (
                "uq_categories_workspace_id_normalized_name",
                ("workspace_id", "normalized_name"),
            ),
            unique_constraints,
        )
        self.assertIn("ck_categories_name_not_blank", check_names)
        self.assertIn(
            (
                "ix_categories_workspace_id_is_active_name",
                ("workspace_id", "is_active", "name"),
            ),
            indexes,
        )

    def test_workspace_relationship_and_foreign_key(self) -> None:
        self.assertEqual(
            inspect(Category).relationships["workspace"].back_populates,
            "categories",
        )
        self.assertEqual(
            inspect(Workspace).relationships["categories"].back_populates,
            "workspace",
        )
        foreign_key = next(iter(Category.__table__.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "workspaces.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")


if __name__ == "__main__":
    unittest.main()
