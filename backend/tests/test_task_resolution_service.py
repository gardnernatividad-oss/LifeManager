import unittest
import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Task, TaskOutcome, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.task import TaskRead
from app.services.task_resolution_service import (
    TaskAlreadyResolved,
    TaskNotFound,
    TaskPermission,
    cancel_task,
    complete_task,
    mark_task_not_completed,
)


class TaskResolutionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.now = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
        self.membership_row = WorkspaceMember(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.MEMBER,
        )

    def task(self, *, scheduled: bool = False, **changes: object) -> Task:
        values = {
            "id": uuid.uuid4(),
            "workspace_id": self.workspace_id,
            "created_by_id": self.user.id,
            "title": "Task",
            "scheduled_at": self.now + (timedelta(days=1) if scheduled else -timedelta(days=1)),
            "outcome": None,
            "resolved_at": None,
            "created_at": self.now - timedelta(days=2),
            "updated_at": self.now - timedelta(days=2),
        }
        values.update(changes)
        return Task(**values)

    def membership(self, value: object = ...):
        result = self.membership_row if value is ... else value
        return patch(
            "app.services.task_resolution_service.get_workspace_membership",
            return_value=result,
        )

    def test_all_terminal_resolutions_set_timestamp_flush_and_derive_status(self) -> None:
        cases = (
            (complete_task, TaskOutcome.COMPLETED, "completed"),
            (mark_task_not_completed, TaskOutcome.NOT_COMPLETED, "not_completed"),
            (cancel_task, TaskOutcome.CANCELLED, "cancelled"),
        )
        for operation, outcome, status in cases:
            for scheduled in (False, True):
                self.db.reset_mock()
                task = self.task(scheduled=scheduled)
                self.db.scalar.return_value = task
                with self.subTest(outcome=outcome, scheduled=scheduled), self.membership(), patch(
                    "app.services.task_resolution_service._utc_now",
                    return_value=self.now,
                ):
                    result = operation(
                        self.db,
                        workspace_id=self.workspace_id,
                        task_id=task.id,
                        current_user=self.user,
                    )
                self.assertIs(result, task)
                self.assertIs(task.outcome, outcome)
                self.assertEqual(task.resolved_at, self.now)
                self.assertEqual(TaskRead.from_task(task, now=self.now).status.value, status)
                self.db.flush.assert_called_once_with()
                self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_task_cannot_be_resolved_twice(self) -> None:
        original_resolved_at = self.now - timedelta(hours=1)
        task = self.task(outcome=TaskOutcome.COMPLETED, resolved_at=original_resolved_at)
        self.db.scalar.return_value = task
        for operation in (complete_task, mark_task_not_completed, cancel_task):
            with self.subTest(operation=operation.__name__), self.membership(), self.assertRaises(TaskAlreadyResolved):
                operation(self.db, workspace_id=self.workspace_id, task_id=task.id, current_user=self.user)
        self.assertIs(task.outcome, TaskOutcome.COMPLETED)
        self.assertEqual(task.resolved_at, original_resolved_at)
        self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_nonmember_is_denied_without_task_lookup_or_writes(self) -> None:
        with self.membership(None), self.assertRaises(TaskPermission):
            complete_task(self.db, workspace_id=self.workspace_id, task_id=uuid.uuid4(), current_user=self.user)
        self.db.scalar.assert_not_called(); self.db.flush.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_missing_or_other_workspace_task_is_not_found_and_query_is_scoped(self) -> None:
        task_id = uuid.uuid4()
        self.db.scalar.return_value = None
        with self.membership(), self.assertRaises(TaskNotFound):
            complete_task(self.db, workspace_id=self.workspace_id, task_id=task_id, current_user=self.user)
        params = tuple(self.db.scalar.call_args.args[0].compile().params.values())
        self.assertIn(task_id, params); self.assertIn(self.workspace_id, params)
        self.db.flush.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
