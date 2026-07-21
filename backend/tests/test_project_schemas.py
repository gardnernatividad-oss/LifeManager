import unittest
import uuid

from datetime import datetime, timezone

from pydantic import ValidationError

from app.models import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate


class ProjectSchemaTests(unittest.TestCase):
    def test_create_and_update_validation(self) -> None:
        self.assertEqual(ProjectCreate(name=" Test ").name, "Test")
        self.assertEqual(ProjectUpdate(description=None).model_dump(exclude_unset=True), {"description": None})
        for payload in ({}, {"name": " "}, {"name": "x" * 101}, {"name": "x", "description": "x" * 501}, {"name": "x", "workspace_id": str(uuid.uuid4())}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ProjectCreate.model_validate(payload)
        with self.assertRaises(ValidationError):
            ProjectUpdate(name=None)

    def test_read_from_model_hides_internal_fields(self) -> None:
        now = datetime.now(timezone.utc)
        project = Project(
            id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="Test",
            normalized_name="test", description=None, is_active=True,
            created_at=now, updated_at=now,
        )
        data = ProjectRead.model_validate(project).model_dump()
        self.assertNotIn("normalized_name", data)
        self.assertEqual(data["name"], "Test")


if __name__ == "__main__":
    unittest.main()
