import unittest
import uuid

from datetime import datetime, timezone

from pydantic import ValidationError

from app.models import Category
from app.schemas import CategoryCreate, CategoryRead, CategoryUpdate


class CategorySchemaTests(unittest.TestCase):
    def test_valid_create_and_partial_update(self) -> None:
        created = CategoryCreate(name="Trabajo")
        updated = CategoryUpdate(description=None)

        self.assertEqual(created.name, "Trabajo")
        self.assertIsNone(created.description)
        self.assertEqual(
            updated.model_dump(exclude_unset=True),
            {"description": None},
        )

    def test_invalid_lengths_and_blank_name_are_rejected(self) -> None:
        invalid_payloads = (
            {"name": "   "},
            {"name": "x" * 101},
            {"name": "Trabajo", "description": "x" * 501},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CategoryCreate.model_validate(payload)

    def test_update_rejects_explicit_null_name_and_protected_fields(self) -> None:
        for payload in (
            {"name": None},
            {"workspace_id": uuid.uuid4()},
            {"normalized_name": "hidden"},
            {"is_active": False},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CategoryUpdate.model_validate(payload)

    def test_read_schema_excludes_normalized_name(self) -> None:
        timestamp = datetime.now(timezone.utc)
        category = Category(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            name="Trabajo",
            normalized_name="trabajo",
            description=None,
            is_active=True,
            created_at=timestamp,
            updated_at=timestamp,
        )

        data = CategoryRead.model_validate(category).model_dump()

        self.assertNotIn("normalized_name", data)
        self.assertEqual(data["name"], "Trabajo")


if __name__ == "__main__":
    unittest.main()
