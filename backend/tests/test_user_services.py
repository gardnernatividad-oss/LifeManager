import unittest
import uuid

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import User
from app.schemas import UserCreate
from app.services.user import register_user


class UserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.db.scalar.return_value = None
        self.user_in = UserCreate(
            email="Ada@Example.COM",
            password="plain-secret",
            first_name="Ada",
            last_name="Lovelace",
        )

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_successful_registration(self, hash_mock: MagicMock) -> None:
        user = register_user(self.db, user_in=self.user_in)

        self.assertIsInstance(user, User)
        self.db.add.assert_called_once_with(user)
        self.db.flush.assert_called_once_with()
        hash_mock.assert_called_once_with("plain-secret")

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_password_is_hashed(self, hash_mock: MagicMock) -> None:
        user = register_user(self.db, user_in=self.user_in)

        self.assertEqual(user.hashed_password, "hashed-secret")
        self.assertNotEqual(user.hashed_password, self.user_in.password)
        self.assertNotIn("password", user.__dict__)
        hash_mock.assert_called_once_with(self.user_in.password)

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_email_is_normalized(self, _hash_mock: MagicMock) -> None:
        user = register_user(self.db, user_in=self.user_in)

        statement = self.db.scalar.call_args.args[0]
        self.assertIn("ada@example.com", statement.compile().params.values())
        self.assertEqual(user.email, "ada@example.com")

    def test_duplicate_email_is_rejected(self) -> None:
        self.db.scalar.return_value = User(email="ada@example.com")

        with (
            patch("app.services.user.hash_password") as hash_mock,
            self.assertRaisesRegex(ValueError, "^Email already registered$"),
        ):
            register_user(self.db, user_in=self.user_in)

        hash_mock.assert_not_called()
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_username_is_generated(self, _hash_mock: MagicMock) -> None:
        user = register_user(self.db, user_in=self.user_in)

        self.assertEqual(len(user.username), 32)
        self.assertEqual(uuid.UUID(hex=user.username).hex, user.username)

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_full_name_is_generated(self, _hash_mock: MagicMock) -> None:
        user_in = UserCreate(
            email="ada@example.com",
            password="plain-secret",
            first_name="  Ada ",
            last_name=" Lovelace  ",
        )

        user = register_user(self.db, user_in=user_in)

        self.assertEqual(user.full_name, "Ada Lovelace")

    @patch("app.services.user.hash_password", return_value="hashed-secret")
    def test_service_never_commits(self, _hash_mock: MagicMock) -> None:
        register_user(self.db, user_in=self.user_in)

        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
