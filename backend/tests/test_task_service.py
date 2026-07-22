import unittest
import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Category, Project, Task, TaskOutcome, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_resolution_service import TaskAlreadyResolved
from app.services.task_service import (
    TaskCategoryInactiveError, TaskNotFoundError, TaskPermissionError,
    TaskProjectInactiveError, create_task, get_task, list_tasks, update_task,
)


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.now = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)

    def member(self, value: object = ...):
        result = self.membership if value is ... else value
        return patch("app.services.task_service.get_workspace_membership", return_value=result)

    def task(self, **changes: object) -> Task:
        values = dict(
            id=uuid.uuid4(), workspace_id=self.workspace_id, created_by_id=self.user.id,
            category_id=None, project_id=None, title="Task", description=None,
            scheduled_at=self.now + timedelta(days=1), outcome=None, resolved_at=None,
            created_at=self.now, updated_at=self.now,
        )
        values.update(changes)
        return Task(**values)

    def test_create_is_unresolved_supports_associations_and_does_not_commit(self) -> None:
        category = Category(id=uuid.uuid4(), workspace_id=self.workspace_id, name="C", normalized_name="c", is_active=True)
        project = Project(id=uuid.uuid4(), workspace_id=self.workspace_id, name="P", normalized_name="p", is_active=True)
        self.db.scalar.side_effect = [category, project]
        with self.member():
            task = create_task(
                self.db, workspace_id=self.workspace_id, current_user=self.user,
                task_in=TaskCreate(title="Task", scheduled_at=self.now, category_id=category.id, project_id=project.id),
            )
        self.assertEqual((task.category_id, task.project_id), (category.id, project.id))
        self.assertIsNone(task.outcome); self.assertIsNone(task.resolved_at)
        self.db.add.assert_called_once_with(task); self.db.flush.assert_called_once()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_create_preserves_inactive_assignment_rules_and_membership(self) -> None:
        inactive = Category(id=uuid.uuid4(), workspace_id=self.workspace_id, name="C", normalized_name="c", is_active=False)
        self.db.scalar.return_value = inactive
        with self.member(), self.assertRaises(TaskCategoryInactiveError):
            create_task(self.db, workspace_id=self.workspace_id, current_user=self.user, task_in=TaskCreate(title="T", scheduled_at=self.now, category_id=inactive.id))
        project = Project(id=uuid.uuid4(), workspace_id=self.workspace_id, name="P", normalized_name="p", is_active=False)
        self.db.scalar.return_value = project
        with self.member(), self.assertRaises(TaskProjectInactiveError):
            create_task(self.db, workspace_id=self.workspace_id, current_user=self.user, task_in=TaskCreate(title="T", scheduled_at=self.now, project_id=project.id))
        with self.member(None), self.assertRaises(TaskPermissionError):
            create_task(self.db, workspace_id=self.workspace_id, current_user=self.user, task_in=TaskCreate(title="T", scheduled_at=self.now))

    def test_list_has_final_scope_order_filters_and_no_writes(self) -> None:
        category = Category(id=uuid.uuid4(), workspace_id=self.workspace_id, name="C", normalized_name="c", is_active=False)
        project = Project(id=uuid.uuid4(), workspace_id=self.workspace_id, name="P", normalized_name="p", is_active=False)
        tasks = [self.task(category_id=category.id, project_id=project.id, outcome=TaskOutcome.COMPLETED, resolved_at=self.now)]
        self.db.scalar.side_effect = [category, project, 1]
        self.db.scalars.return_value.all.return_value = tasks
        with self.member():
            result, total = list_tasks(self.db, workspace_id=self.workspace_id, current_user=self.user, category_id=category.id, project_id=project.id)
        sql = str(self.db.scalars.call_args.args[0])
        self.assertNotIn("is_archived", sql)
        self.assertIn("ORDER BY tasks.scheduled_at, tasks.created_at, tasks.id", sql)
        self.assertEqual((result, total), (tasks, 1))
        self.db.flush.assert_not_called(); self.db.commit.assert_not_called()

    def test_get_is_workspace_scoped_and_resolved_tasks_are_readable(self) -> None:
        task = self.task(outcome=TaskOutcome.COMPLETED, resolved_at=self.now)
        self.db.scalar.return_value = task
        with self.member():
            self.assertIs(get_task(self.db, workspace_id=self.workspace_id, task_id=task.id, current_user=self.user), task)
        params = self.db.scalar.call_args.args[0].compile().params.values()
        self.assertIn(self.workspace_id, params); self.assertIn(task.id, params)
        self.db.scalar.return_value = None
        with self.member(), self.assertRaises(TaskNotFoundError):
            get_task(self.db, workspace_id=self.workspace_id, task_id=uuid.uuid4(), current_user=self.user)

    def test_update_metadata_schedule_and_association_semantics(self) -> None:
        task = self.task(category_id=uuid.uuid4(), project_id=uuid.uuid4())
        new_schedule = self.now + timedelta(days=2)
        self.db.scalar.return_value = task
        with self.member():
            update_task(self.db, workspace_id=self.workspace_id, task_id=task.id, current_user=self.user, task_in=TaskUpdate(title="Changed", description=None, scheduled_at=new_schedule))
        self.assertEqual(task.title, "Changed"); self.assertIsNone(task.description)
        self.assertEqual(task.scheduled_at, new_schedule)
        self.assertIsNotNone(task.category_id); self.assertIsNotNone(task.project_id)
        self.assertIsNone(task.outcome); self.assertIsNone(task.resolved_at)

    def test_resolved_task_is_immutable_even_for_equivalent_values(self) -> None:
        task = self.task(outcome=TaskOutcome.COMPLETED, resolved_at=self.now)
        self.db.scalar.return_value = task
        for task_in in (
            TaskUpdate(title="Changed"),
            TaskUpdate(description="Changed"),
            TaskUpdate(scheduled_at=task.scheduled_at),
            TaskUpdate(category_id=uuid.uuid4()),
            TaskUpdate(project_id=uuid.uuid4()),
        ):
            with self.subTest(changes=task_in.model_dump(exclude_unset=True)), self.member(), self.assertRaises(TaskAlreadyResolved):
                update_task(self.db, workspace_id=self.workspace_id, task_id=task.id, current_user=self.user, task_in=task_in)
        self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
