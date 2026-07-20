import unittest
import uuid

from datetime import datetime, timezone

from pydantic import ValidationError

from app.models import User
from app.schemas import UserCreate, UserRead


class UserSchemaTests(unittest.TestCase):
    def test_user_create_validates_email(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate(
                email="not-an-email",
                password="secret",
                first_name="Ada",
                last_name="Lovelace",
            )

    def test_user_read_does_not_expose_password_data(self) -> None:
        timestamp = datetime.now(timezone.utc)
        user = User(
            id=uuid.uuid4(),
            email="ada@example.com",
            hashed_password="hashed-secret",
            first_name="Ada",
            last_name="Lovelace",
            is_active=True,
            is_verified=False,
            created_at=timestamp,
            updated_at=timestamp,
        )

        serialized = UserRead.model_validate(user).model_dump()

        self.assertNotIn("password", serialized)
        self.assertNotIn("hashed_password", serialized)
        self.assertEqual(serialized["email"], "ada@example.com")


if __name__ == "__main__":
    unittest.main()
