import unittest

from sqlalchemy import CheckConstraint, inspect

from app.models import Category, Project, Task, TaskOutcome, TaskStatus
from app.models.base import Base


class TaskModelTests(unittest.TestCase):
    def test_final_fields_and_removed_legacy_fields(self) -> None:
        columns = Task.__table__.columns
        self.assertEqual(
            set(columns.keys()),
            {
                "id", "workspace_id", "created_by_id", "category_id",
                "project_id", "task_series_id", "title", "description", "scheduled_at",
                "outcome", "resolved_at", "created_at", "updated_at",
            },
        )
        self.assertFalse(columns.scheduled_at.nullable)
        self.assertTrue(columns.outcome.nullable)
        self.assertTrue(columns.resolved_at.nullable)
        self.assertIs(Base.metadata.tables["tasks"], Task.__table__)

    def test_enums_constraints_and_indexes(self) -> None:
        self.assertEqual([item.value for item in TaskOutcome], ["completed", "not_completed", "cancelled"])
        self.assertEqual([item.value for item in TaskStatus], ["scheduled", "pending", "completed", "not_completed", "cancelled"])
        checks = {c.name for c in Task.__table__.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("ck_tasks_outcome_resolved_at_consistent", checks)
        indexes = {i.name: tuple(c.name for c in i.columns) for i in Task.__table__.indexes}
        self.assertEqual(indexes["ix_tasks_workspace_id_outcome_scheduled_at"], ("workspace_id", "outcome", "scheduled_at"))
        self.assertEqual(indexes["ix_tasks_workspace_id_category_id"], ("workspace_id", "category_id"))
        self.assertEqual(indexes["ix_tasks_workspace_id_project_id"], ("workspace_id", "project_id"))

    def test_foreign_keys_and_relationships_are_preserved(self) -> None:
        foreign_keys = {fk.parent.name: fk for fk in Task.__table__.foreign_keys}
        self.assertEqual((foreign_keys["workspace_id"].target_fullname, foreign_keys["workspace_id"].ondelete), ("workspaces.id", "CASCADE"))
        self.assertEqual((foreign_keys["created_by_id"].target_fullname, foreign_keys["created_by_id"].ondelete), ("users.id", "RESTRICT"))
        self.assertEqual((foreign_keys["category_id"].target_fullname, foreign_keys["category_id"].ondelete), ("categories.id", "SET NULL"))
        self.assertEqual((foreign_keys["project_id"].target_fullname, foreign_keys["project_id"].ondelete), ("projects.id", "SET NULL"))
        self.assertEqual((foreign_keys["task_series_id"].target_fullname, foreign_keys["task_series_id"].ondelete), ("task_series.id", "SET NULL"))
        self.assertEqual(inspect(Task).relationships.category.back_populates, "tasks")
        self.assertEqual(inspect(Category).relationships.tasks.back_populates, "category")
        self.assertEqual(inspect(Task).relationships.project.back_populates, "tasks")
        self.assertEqual(inspect(Project).relationships.tasks.back_populates, "project")


if __name__ == "__main__":
    unittest.main()
