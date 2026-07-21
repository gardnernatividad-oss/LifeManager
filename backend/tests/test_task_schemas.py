import unittest
import uuid

from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.models import Task, TaskOutcome, TaskStatus
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate, derive_task_status


class TaskSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)

    def task(self, **changes: object) -> Task:
        values = dict(
            id=uuid.uuid4(), workspace_id=uuid.uuid4(), created_by_id=uuid.uuid4(),
            category_id=None, project_id=None, title="Task", description=None,
            scheduled_at=self.now + timedelta(hours=1), outcome=None, resolved_at=None,
            created_at=self.now, updated_at=self.now,
        )
        values.update(changes)
        return Task(**values)

    def test_create_requires_aware_schedule_and_rejects_legacy_fields(self) -> None:
        schema = TaskCreate(title=" Task ", scheduled_at=self.now)
        self.assertEqual(schema.title, "Task")
        self.assertEqual(schema.scheduled_at, self.now)
        for payload in (
            {"title": "Task"},
            {"title": "Task", "scheduled_at": datetime(2026, 1, 1)},
            {"title": "Task", "scheduled_at": self.now.isoformat(), "status": "pending"},
            {"title": "Task", "scheduled_at": self.now.isoformat(), "priority": "high"},
            {"title": "Task", "scheduled_at": self.now.isoformat(), "outcome": "completed"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                TaskCreate.model_validate(payload)

    def test_update_omission_and_explicit_null_rules(self) -> None:
        self.assertEqual(TaskUpdate().model_dump(exclude_unset=True), {})
        self.assertEqual(TaskUpdate(description=None, category_id=None, project_id=None).model_dump(exclude_unset=True), {"description": None, "category_id": None, "project_id": None})
        for payload in ({"title": None}, {"scheduled_at": None}, {"resolved_at": self.now}, {"is_archived": True}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                TaskUpdate.model_validate(payload)

    def test_status_derivation_and_final_read_contract(self) -> None:
        cases = (
            (self.task(scheduled_at=self.now + timedelta(seconds=1)), TaskStatus.SCHEDULED),
            (self.task(scheduled_at=self.now), TaskStatus.PENDING),
            (self.task(scheduled_at=self.now - timedelta(days=1)), TaskStatus.PENDING),
            (self.task(outcome=TaskOutcome.COMPLETED, resolved_at=self.now), TaskStatus.COMPLETED),
            (self.task(outcome=TaskOutcome.NOT_COMPLETED, resolved_at=self.now), TaskStatus.NOT_COMPLETED),
            (self.task(outcome=TaskOutcome.CANCELLED, resolved_at=self.now), TaskStatus.CANCELLED),
        )
        for task, expected in cases:
            with self.subTest(expected=expected):
                self.assertIs(derive_task_status(task, now=self.now), expected)
                read = TaskRead.from_task(task, now=self.now)
                self.assertIs(read.status, expected)
                self.assertEqual(
                    set(read.model_dump()),
                    {"id", "workspace_id", "created_by_id", "category_id", "project_id", "title", "description", "scheduled_at", "status", "resolved_at", "created_at", "updated_at"},
                )


if __name__ == "__main__":
    unittest.main()
