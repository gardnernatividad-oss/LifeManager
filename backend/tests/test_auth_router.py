import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.workspaces import get_db
from app.main import app
from app.models import User


class AuthRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.payload = {
            "email": "ada@example.com",
            "password": "plain-secret",
            "first_name": "Ada",
            "last_name": "Lovelace",
        }

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def make_user(self) -> User:
        timestamp = datetime.now(timezone.utc)
        return User(
            id=uuid.uuid4(),
            email="ada@example.com",
            hashed_password="hashed-secret",
            first_name="Ada",
            last_name="Lovelace",
            username=uuid.uuid4().hex,
            full_name="Ada Lovelace",
            is_active=True,
            is_verified=False,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def test_register_returns_created_user_without_password_data(self) -> None:
        user = self.make_user()

        with patch(
            "app.api.routes.auth.register_user",
            return_value=user,
        ) as register_mock:
            response = self.client.post("/auth/register", json=self.payload)

        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data["id"], str(user.id))
        self.assertEqual(response_data["email"], user.email)
        self.assertNotIn("password", response_data)
        self.assertNotIn("hashed_password", response_data)
        register_mock.assert_called_once()
        called_user_in = register_mock.call_args.kwargs["user_in"]
        self.assertEqual(called_user_in.email, self.payload["email"])
        self.assertEqual(called_user_in.password, self.payload["password"])
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(user)

    def test_duplicate_email_returns_conflict_and_rolls_back(self) -> None:
        with patch(
            "app.api.routes.auth.register_user",
            side_effect=ValueError("Email already registered"),
        ):
            response = self.client.post("/auth/register", json=self.payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Email already registered"})
        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_invalid_email_returns_unprocessable_entity(self) -> None:
        invalid_payload = {**self.payload, "email": "not-an-email"}

        with patch("app.api.routes.auth.register_user") as register_mock:
            response = self.client.post("/auth/register", json=invalid_payload)

        self.assertEqual(response.status_code, 422)
        register_mock.assert_not_called()
        self.db.commit.assert_not_called()

    def test_existing_routes_remain_registered(self) -> None:
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/workspaces").status_code, 422)


if __name__ == "__main__":
    unittest.main()
