import unittest
import uuid

from datetime import datetime, timezone

from pydantic import ValidationError

from app.models import Task, TaskPriority, TaskStatus
from app.schemas import TaskCreate, TaskListResponse, TaskRead, TaskUpdate


class TaskCreateSchemaTests(unittest.TestCase):
    def test_valid_minimal_payload_uses_defaults(self) -> None:
        schema = TaskCreate(title="Plan week")

        self.assertEqual(schema.title, "Plan week")
        self.assertIsNone(schema.description)
        self.assertEqual(schema.status, TaskStatus.TODO)
        self.assertEqual(schema.priority, TaskPriority.MEDIUM)
        self.assertIsNone(schema.due_at)
        self.assertEqual(schema.position, 0)

    def test_title_is_trimmed(self) -> None:
        self.assertEqual(TaskCreate(title="  Plan week  ").title, "Plan week")

    def test_invalid_titles_are_rejected(self) -> None:
        for title in ("", "   ", "x" * 256):
            with self.subTest(title_length=len(title)):
                with self.assertRaises(ValidationError):
                    TaskCreate(title=title)

    def test_negative_position_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            TaskCreate(title="Plan week", position=-1)

    def test_unknown_and_protected_fields_are_rejected(self) -> None:
        for field in ("unknown", "workspace_id", "created_by_id"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    TaskCreate.model_validate({"title": "Plan week", field: uuid.uuid4()})

    def test_enum_values_are_accepted_and_invalid_values_rejected(self) -> None:
        schema = TaskCreate(title="Plan week", status="done", priority="urgent")

        self.assertEqual(schema.status, TaskStatus.DONE)
        self.assertEqual(schema.priority, TaskPriority.URGENT)
        with self.assertRaises(ValidationError):
            TaskCreate(title="Plan week", status="invalid")

    def test_nullable_due_at_is_accepted(self) -> None:
        self.assertIsNone(TaskCreate(title="Plan week", due_at=None).due_at)

    def test_optional_category_id_accepts_uuid_and_null(self) -> None:
        category_id = uuid.uuid4()

        self.assertIsNone(TaskCreate(title="No category").category_id)
        self.assertEqual(
            TaskCreate(title="Categorized", category_id=category_id).category_id,
            category_id,
        )
        self.assertIsNone(TaskCreate(title="No category", category_id=None).category_id)
        with self.assertRaises(ValidationError):
            TaskCreate(title="Invalid", category_id="not-a-uuid")

    def test_optional_project_id_accepts_uuid_and_null(self) -> None:
        project_id = uuid.uuid4()
        self.assertIsNone(TaskCreate(title="No project").project_id)
        self.assertEqual(
            TaskCreate(title="Project", project_id=project_id).project_id,
            project_id,
        )
        self.assertIsNone(TaskCreate(title="No project", project_id=None).project_id)
        with self.assertRaises(ValidationError):
            TaskCreate(title="Invalid", project_id="not-a-uuid")


class TaskUpdateSchemaTests(unittest.TestCase):
    def test_empty_and_partial_payloads_are_accepted(self) -> None:
        self.assertEqual(TaskUpdate().model_dump(exclude_unset=True), {})
        self.assertEqual(
            TaskUpdate(priority=TaskPriority.HIGH).model_dump(exclude_unset=True),
            {"priority": TaskPriority.HIGH},
        )

    def test_nullable_fields_may_be_explicitly_cleared(self) -> None:
        schema = TaskUpdate(description=None, due_at=None)

        self.assertEqual(
            schema.model_dump(exclude_unset=True),
            {"description": None, "due_at": None},
        )

    def test_invalid_title_and_position_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            TaskUpdate(title="   ")
        with self.assertRaises(ValidationError):
            TaskUpdate(position=-1)

    def test_explicit_null_title_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            TaskUpdate(title=None)

    def test_unknown_and_protected_fields_are_rejected(self) -> None:
        for field in ("unknown", "workspace_id", "completed_at"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    TaskUpdate.model_validate({field: uuid.uuid4()})

    def test_category_update_distinguishes_omission_uuid_and_null(self) -> None:
        category_id = uuid.uuid4()

        self.assertNotIn("category_id", TaskUpdate().model_dump(exclude_unset=True))
        self.assertEqual(
            TaskUpdate(category_id=category_id).model_dump(exclude_unset=True),
            {"category_id": category_id},
        )
        self.assertEqual(
            TaskUpdate(category_id=None).model_dump(exclude_unset=True),
            {"category_id": None},
        )

    def test_project_update_distinguishes_omission_uuid_and_null(self) -> None:
        project_id = uuid.uuid4()
        self.assertNotIn("project_id", TaskUpdate().model_dump(exclude_unset=True))
        self.assertEqual(
            TaskUpdate(project_id=project_id).model_dump(exclude_unset=True),
            {"project_id": project_id},
        )
        self.assertEqual(
            TaskUpdate(project_id=None).model_dump(exclude_unset=True),
            {"project_id": None},
        )


class TaskReadSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timestamp = datetime.now(timezone.utc)
        self.task = Task(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            category_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            title="Plan week",
            description=None,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            due_at=self.timestamp,
            completed_at=None,
            position=2,
            is_archived=False,
            created_at=self.timestamp,
            updated_at=self.timestamp,
        )

    def test_validates_from_task_and_exposes_expected_fields(self) -> None:
        schema = TaskRead.model_validate(self.task)

        self.assertEqual(
            set(schema.model_dump()),
            {
                "id",
                "workspace_id",
                "created_by_id",
                "category_id",
                "project_id",
                "title",
                "description",
                "status",
                "priority",
                "due_at",
                "completed_at",
                "position",
                "is_archived",
                "created_at",
                "updated_at",
            },
        )
        self.assertNotIn("workspace", schema.model_dump())
        self.assertNotIn("created_by", schema.model_dump())
        self.assertEqual(schema.category_id, self.task.category_id)
        self.assertEqual(schema.project_id, self.task.project_id)

    def test_json_serializes_enums_as_stable_values(self) -> None:
        serialized = TaskRead.model_validate(self.task).model_dump_json()

        self.assertIn('"status":"in_progress"', serialized)
        self.assertIn('"priority":"high"', serialized)

    def test_list_response_accepts_items_and_rejects_negative_total(self) -> None:
        task = TaskRead.model_validate(self.task)
        response = TaskListResponse(items=[task], total=1)

        self.assertEqual(response.items, [task])
        self.assertEqual(response.total, 1)
        with self.assertRaises(ValidationError):
            TaskListResponse(items=[], total=-1)


if __name__ == "__main__":
    unittest.main()
