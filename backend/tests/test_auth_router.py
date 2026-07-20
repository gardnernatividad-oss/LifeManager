import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.workspaces import get_db
from app.core.config import settings
from app.core.tokens import decode_access_token
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
        self.secret_key_patch = patch.object(
            settings,
            "SECRET_KEY",
            "test-secret-key-that-is-at-least-32-bytes",
        )
        self.secret_key_patch.start()

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.secret_key_patch.stop()

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

    def test_login_returns_access_token_for_valid_credentials(self) -> None:
        user = self.make_user()

        with patch(
            "app.api.routes.auth.authenticate_user",
            return_value=user,
        ) as authenticate_mock:
            response = self.client.post(
                "/auth/login",
                json={
                    "email": "ada@example.com",
                    "password": "plain-secret",
                },
            )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIsInstance(response_data["access_token"], str)
        self.assertEqual(response_data["access_token"].count("."), 2)
        self.assertEqual(response_data["token_type"], "bearer")
        self.assertEqual(
            decode_access_token(response_data["access_token"]),
            str(user.id),
        )
        authenticate_mock.assert_called_once_with(
            self.db,
            email="ada@example.com",
            password="plain-secret",
        )
        self.assertNotIn("password", response_data)
        self.assertNotIn("hashed_password", response_data)
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.refresh.assert_not_called()
        self.db.rollback.assert_not_called()

    def test_invalid_credentials_return_unauthorized(self) -> None:
        with patch(
            "app.api.routes.auth.authenticate_user",
            return_value=None,
        ):
            response = self.client.post(
                "/auth/login",
                json={
                    "email": "missing@example.com",
                    "password": "wrong-secret",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Incorrect email or password"},
        )
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_inactive_user_result_returns_same_unauthorized_response(self) -> None:
        with patch(
            "app.api.routes.auth.authenticate_user",
            return_value=None,
        ):
            response = self.client.post(
                "/auth/login",
                json={
                    "email": "inactive@example.com",
                    "password": "plain-secret",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Incorrect email or password"},
        )
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_login_rejects_invalid_email(self) -> None:
        with patch("app.api.routes.auth.authenticate_user") as authenticate_mock:
            response = self.client.post(
                "/auth/login",
                json={
                    "email": "not-an-email",
                    "password": "plain-secret",
                },
            )

        self.assertEqual(response.status_code, 422)
        authenticate_mock.assert_not_called()

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
        self.assertEqual(self.client.post("/auth/register", json={}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
