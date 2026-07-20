import unittest
import uuid

from sqlalchemy import inspect

from app.models import Task, TaskPriority, TaskStatus, User, Workspace
from app.models.base import Base


class TaskModelTests(unittest.TestCase):
    def test_task_can_be_instantiated_with_required_fields(self) -> None:
        task = Task(
            workspace_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            title="Prepare weekly plan",
        )

        self.assertEqual(task.title, "Prepare weekly plan")

    def test_task_defaults_are_configured(self) -> None:
        columns = Task.__table__.columns

        self.assertIs(columns["status"].default.arg, TaskStatus.TODO)
        self.assertIs(columns["priority"].default.arg, TaskPriority.MEDIUM)
        self.assertEqual(columns["position"].default.arg, 0)
        self.assertIs(columns["is_archived"].default.arg, False)

    def test_task_server_defaults_are_configured(self) -> None:
        columns = Task.__table__.columns

        self.assertEqual(str(columns["status"].server_default.arg), "'todo'::taskstatus")
        self.assertEqual(
            str(columns["priority"].server_default.arg),
            "'medium'::taskpriority",
        )
        self.assertEqual(str(columns["position"].server_default.arg), "0")
        self.assertEqual(str(columns["is_archived"].server_default.arg), "false")

    def test_nullable_scheduling_fields_are_allowed(self) -> None:
        columns = Task.__table__.columns

        self.assertTrue(columns["due_at"].nullable)
        self.assertTrue(columns["completed_at"].nullable)

    def test_enum_values_are_stable_strings(self) -> None:
        self.assertEqual(
            [status.value for status in TaskStatus],
            ["todo", "in_progress", "done", "canceled"],
        )
        self.assertEqual(
            [priority.value for priority in TaskPriority],
            ["low", "medium", "high", "urgent"],
        )

    def test_relationships_are_bidirectional(self) -> None:
        task_relationships = inspect(Task).relationships

        self.assertEqual(task_relationships["workspace"].back_populates, "tasks")
        self.assertEqual(task_relationships["created_by"].back_populates, "created_tasks")
        self.assertEqual(
            inspect(Workspace).relationships["tasks"].back_populates,
            "workspace",
        )
        self.assertEqual(
            inspect(User).relationships["created_tasks"].back_populates,
            "created_by",
        )

    def test_foreign_keys_and_indexes_exist(self) -> None:
        foreign_key_targets = {
            foreign_key.target_fullname
            for foreign_key in Task.__table__.foreign_keys
        }
        indexed_column_sets = {
            tuple(column.name for column in index.columns)
            for index in Task.__table__.indexes
        }

        self.assertEqual(
            foreign_key_targets,
            {"workspaces.id", "users.id"},
        )
        self.assertIn(("workspace_id",), indexed_column_sets)
        self.assertIn(("created_by_id",), indexed_column_sets)
        self.assertIn(("due_at",), indexed_column_sets)
        self.assertIn(
            ("workspace_id", "status", "position"),
            indexed_column_sets,
        )

    def test_foreign_key_delete_behavior_is_explicit(self) -> None:
        foreign_keys = {
            foreign_key.parent.name: foreign_key
            for foreign_key in Task.__table__.foreign_keys
        }

        self.assertEqual(foreign_keys["workspace_id"].ondelete, "CASCADE")
        self.assertEqual(foreign_keys["created_by_id"].ondelete, "RESTRICT")

    def test_task_is_registered_in_metadata(self) -> None:
        self.assertIs(Base.metadata.tables["tasks"], Task.__table__)


if __name__ == "__main__":
    unittest.main()
