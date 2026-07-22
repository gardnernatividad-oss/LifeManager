import unittest
import uuid

from datetime import datetime, timezone

from pydantic import ValidationError

from app.models import Workspace
from app.schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate


class WorkspaceSchemaTests(unittest.TestCase):
    def test_workspace_create_requires_name(self) -> None:
        with self.assertRaises(ValidationError):
            WorkspaceCreate()

    def test_workspace_create_description_is_optional(self) -> None:
        schema = WorkspaceCreate(name="Personal")

        self.assertIsNone(schema.description)

    def test_workspace_update_accepts_partial_updates(self) -> None:
        empty_update = WorkspaceUpdate()
        name_update = WorkspaceUpdate(name="Family")
        description_update = WorkspaceUpdate(description="Shared workspace")

        self.assertEqual(empty_update.model_dump(exclude_unset=True), {})
        self.assertEqual(name_update.model_dump(exclude_unset=True), {"name": "Family"})
        self.assertEqual(
            description_update.model_dump(exclude_unset=True),
            {"description": "Shared workspace"},
        )

    def test_workspace_read_validates_from_orm_object(self) -> None:
        workspace_id = uuid.uuid4()
        timestamp = datetime.now(timezone.utc)
        workspace = Workspace(
            id=workspace_id,
            name="Personal",
            description=None,
            timezone="America/Lima",
            created_at=timestamp,
            updated_at=timestamp,
        )

        schema = WorkspaceRead.model_validate(workspace)

        self.assertEqual(schema.id, workspace_id)
        self.assertEqual(schema.name, "Personal")
        self.assertIsNone(schema.description)
        self.assertEqual(schema.timezone, "America/Lima")
        self.assertEqual(schema.created_at, timestamp)
        self.assertEqual(schema.updated_at, timestamp)


if __name__ == "__main__":
    unittest.main()
