import unittest

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models import Project, Workspace
from app.models.base import Base


class ProjectModelTests(unittest.TestCase):
    def test_metadata_columns_constraints_indexes_and_relationships(self) -> None:
        table = Project.__table__
        self.assertIs(Base.metadata.tables["projects"], table)
        self.assertEqual(table.c.name.type.length, 100)
        self.assertEqual(table.c.description.type.length, 500)
        self.assertFalse(table.c.workspace_id.nullable)
        self.assertFalse(table.c.is_active.nullable)
        self.assertIs(table.c.is_active.default.arg, True)
        self.assertEqual(str(table.c.is_active.server_default.arg), "true")
        self.assertIn(
            "uq_projects_workspace_id_normalized_name",
            {c.name for c in table.constraints if isinstance(c, UniqueConstraint)},
        )
        self.assertIn(
            "ck_projects_name_not_blank",
            {c.name for c in table.constraints if isinstance(c, CheckConstraint)},
        )
        index = next(i for i in table.indexes if i.name == "ix_projects_workspace_id_is_active_name")
        self.assertEqual([c.name for c in index.columns], ["workspace_id", "is_active", "name"])
        foreign_key = next(iter(table.c.workspace_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "workspaces.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")
        self.assertEqual(Project.workspace.property.back_populates, "projects")
        self.assertEqual(Workspace.projects.property.back_populates, "workspace")


if __name__ == "__main__":
    unittest.main()
