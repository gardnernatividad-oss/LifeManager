import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Task, TaskStatus, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas import TaskCreate, TaskUpdate
from app.services.task_service import (
    TaskNotFoundError,
    TaskPermissionError,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.membership = WorkspaceMember(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.MEMBER,
        )

    def assert_no_transaction_control(self) -> None:
        self.db.commit.assert_not_called()
        self.db.rollback.assert_not_called()

    def assert_no_writes(self) -> None:
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.delete.assert_not_called()
        self.assert_no_transaction_control()

    def membership_patch(self, membership: WorkspaceMember | None = None):
        return patch(
            "app.services.task_service.get_workspace_membership",
            return_value=self.membership if membership is None else membership,
        )

    def make_task(self, **overrides: object) -> Task:
        values: dict[str, object] = {
            "id": uuid.uuid4(),
            "workspace_id": self.workspace_id,
            "created_by_id": self.user.id,
            "title": "Original",
            "description": "Details",
            "status": TaskStatus.TODO,
            "due_at": datetime.now(timezone.utc),
            "completed_at": None,
            "position": 1,
            "is_archived": False,
        }
        values.update(overrides)
        return Task(**values)

    def test_member_can_create_using_context_identifiers(self) -> None:
        task_in = TaskCreate(title="New task", status=TaskStatus.DONE)

        with self.membership_patch() as membership_mock:
            task = create_task(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
                task_in=task_in,
            )

        membership_mock.assert_called_once_with(
            self.db,
            workspace_id=self.workspace_id,
            user_id=self.user.id,
        )
        self.assertEqual(task.workspace_id, self.workspace_id)
        self.assertEqual(task.created_by_id, self.user.id)
        self.assertNotIn("workspace_id", task_in.model_dump())
        self.assertNotIn("created_by_id", task_in.model_dump())
        self.assertIsNone(task.completed_at)
        self.db.add.assert_called_once_with(task)
        self.db.flush.assert_called_once_with()
        self.assert_no_transaction_control()

    def test_membership_is_required_for_list(self) -> None:
        with (
            patch(
                "app.services.task_service.get_workspace_membership",
                return_value=None,
            ),
            self.assertRaisesRegex(TaskPermissionError, "Workspace access denied"),
        ):
            list_tasks(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )

        self.assert_no_writes()

    def test_list_is_scoped_non_archived_ordered_and_counted(self) -> None:
        tasks = [self.make_task(), self.make_task(position=2)]
        self.db.scalars.return_value.all.return_value = tasks
        self.db.scalar.return_value = 2

        with self.membership_patch():
            result, total = list_tasks(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )

        statement = self.db.scalars.call_args.args[0]
        count_statement = self.db.scalar.call_args.args[0]
        sql = str(statement)
        self.assertIn(self.workspace_id, statement.compile().params.values())
        self.assertIn("tasks.is_archived IS false", sql)
        self.assertIn("tasks.workspace_id", str(count_statement))
        self.assertIn("ORDER BY tasks.position, tasks.created_at, tasks.id", sql)
        self.assertEqual(result, tasks)
        self.assertEqual(total, 2)
        self.assert_no_writes()

    def test_get_requires_membership_and_scopes_both_identifiers(self) -> None:
        task = self.make_task()
        self.db.scalar.return_value = task

        with self.membership_patch() as membership_mock:
            result = get_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
            )

        membership_mock.assert_called_once()
        statement = self.db.scalar.call_args.args[0]
        parameters = statement.compile().params.values()
        self.assertIn(self.workspace_id, parameters)
        self.assertIn(task.id, parameters)
        self.assertIs(result, task)
        self.assert_no_writes()

    def test_missing_or_cross_workspace_task_is_not_exposed(self) -> None:
        self.db.scalar.return_value = None

        with self.membership_patch(), self.assertRaisesRegex(
            TaskNotFoundError,
            "Task not found",
        ):
            get_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=uuid.uuid4(),
                current_user=self.user,
            )

        self.assert_no_writes()

    def test_update_applies_only_explicit_nullable_fields(self) -> None:
        due_at = datetime.now(timezone.utc)
        task = self.make_task(due_at=due_at)
        original_ids = (task.id, task.workspace_id, task.created_by_id)
        self.db.scalar.return_value = task

        with self.membership_patch():
            result = update_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
                task_in=TaskUpdate(description=None, due_at=None),
            )

        self.assertIs(result, task)
        self.assertEqual(task.title, "Original")
        self.assertIsNone(task.description)
        self.assertIsNone(task.due_at)
        self.assertIsNone(task.completed_at)
        self.assertEqual((task.id, task.workspace_id, task.created_by_id), original_ids)
        self.db.flush.assert_called_once_with()
        self.db.add.assert_not_called()
        self.assert_no_transaction_control()

    def test_update_preserves_protected_and_omitted_fields(self) -> None:
        timestamp = datetime.now(timezone.utc)
        task = self.make_task(created_at=timestamp, updated_at=timestamp)
        protected_values = {
            "id": task.id,
            "workspace_id": task.workspace_id,
            "created_by_id": task.created_by_id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        original_description = task.description
        self.db.scalar.return_value = task

        with self.membership_patch():
            result = update_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
                task_in=TaskUpdate(title="Updated title"),
            )

        self.assertIs(result, task)
        self.assertEqual(task.title, "Updated title")
        self.assertEqual(task.description, original_description)
        self.assertEqual(
            {
                "id": task.id,
                "workspace_id": task.workspace_id,
                "created_by_id": task.created_by_id,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            },
            protected_values,
        )
        self.db.flush.assert_called_once_with()

    def test_creator_may_delete(self) -> None:
        task = self.make_task()
        self.db.scalar.return_value = task

        with self.membership_patch():
            result = delete_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
            )

        self.assertIsNone(result)
        self.db.delete.assert_called_once_with(task)
        self.db.flush.assert_called_once_with()
        self.assert_no_transaction_control()

    def test_workspace_owner_may_delete_another_users_task(self) -> None:
        task = self.make_task(created_by_id=uuid.uuid4())
        self.db.scalar.return_value = task
        owner_membership = WorkspaceMember(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.OWNER,
        )

        with patch(
            "app.services.task_service.get_workspace_membership",
            return_value=owner_membership,
        ):
            delete_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
            )

        self.db.delete.assert_called_once_with(task)
        self.db.flush.assert_called_once_with()
        self.assert_no_transaction_control()

    def test_non_creator_member_cannot_delete(self) -> None:
        task = self.make_task(created_by_id=uuid.uuid4())
        self.db.scalar.return_value = task

        with self.membership_patch(), self.assertRaisesRegex(
            TaskPermissionError,
            "Insufficient task permissions",
        ):
            delete_task(
                self.db,
                workspace_id=self.workspace_id,
                task_id=task.id,
                current_user=self.user,
            )

        self.db.delete.assert_not_called()
        self.db.flush.assert_not_called()
        self.assert_no_transaction_control()


if __name__ == "__main__":
    unittest.main()
