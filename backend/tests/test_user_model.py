import unittest

from sqlalchemy import UniqueConstraint

from app.models import User


class UserModelMetadataTests(unittest.TestCase):
    def test_email_is_unique(self) -> None:
        unique_column_sets = {
            tuple(column.name for column in constraint.columns)
            for constraint in User.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }

        self.assertIn(("email",), unique_column_sets)

    def test_email_has_an_index(self) -> None:
        email_indexes = [
            index
            for index in User.__table__.indexes
            if tuple(column.name for column in index.columns) == ("email",)
        ]

        self.assertEqual(len(email_indexes), 1)
        self.assertFalse(email_indexes[0].unique)

    def test_boolean_defaults(self) -> None:
        self.assertIs(User.__table__.columns["is_active"].default.arg, True)
        self.assertIs(User.__table__.columns["is_verified"].default.arg, False)

    def test_stores_only_hashed_password(self) -> None:
        column_names = set(User.__table__.columns.keys())

        self.assertIn("hashed_password", column_names)
        self.assertNotIn("password", column_names)
        self.assertNotIn("password_hash", column_names)

    def test_retains_legacy_identity_and_preference_columns(self) -> None:
        column_names = set(User.__table__.columns.keys())

        self.assertTrue(
            {"username", "full_name", "timezone", "language"}
            <= column_names
        )


if __name__ == "__main__":
    unittest.main()
