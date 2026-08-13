import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.tokens import decode_access_token
from app.main import app
from app.models import User
from app.services.user import EmailAlreadyRegisteredError


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
            timezone="America/Lima",
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

    def test_versioned_login_preserves_existing_login_behavior(self) -> None:
        user = self.make_user()

        with patch(
            "app.api.routes.auth.authenticate_user",
            return_value=user,
        ):
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": "ada@example.com",
                    "password": "plain-secret",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertEqual(
            decode_access_token(response.json()["access_token"]),
            str(user.id),
        )
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.refresh.assert_not_called()
        self.db.rollback.assert_not_called()

    def test_authenticated_user_returns_user_read_without_writes(self) -> None:
        user = self.make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "timezone": user.timezone,
            },
        )
        self.db.add.assert_not_called()
        self.db.delete.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.refresh.assert_not_called()
        self.db.rollback.assert_not_called()

    def test_authenticated_user_requires_bearer_token(self) -> None:
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_authenticated_user_rejects_invalid_token(self) -> None:
        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer malformed-token"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Could not validate credentials"})
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_authenticated_user_rejects_expired_token(self) -> None:
        from datetime import timedelta

        from app.core.tokens import create_access_token

        token = create_access_token(
            subject=str(uuid.uuid4()),
            expires_delta=timedelta(seconds=-1),
        )

        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Could not validate credentials"})
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

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

    def test_registration_returns_target_user_and_commits_once(self) -> None:
        user = self.make_user()

        with patch("app.api.routes.auth.register_user", return_value=user) as register_mock:
            response = self.client.post("/api/v1/auth/register", json=self.payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["timezone"], "America/Lima")
        self.assertNotIn("password", response.json())
        self.assertNotIn("hashed_password", response.json())
        register_mock.assert_called_once()
        self.assertEqual(register_mock.call_args.kwargs["user_in"].email, self.payload["email"])
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(user)
        self.db.rollback.assert_not_called()

    def test_duplicate_registration_rolls_back_and_returns_conflict(self) -> None:
        with patch(
            "app.api.routes.auth.register_user",
            side_effect=EmailAlreadyRegisteredError("Email already registered"),
        ):
            response = self.client.post("/api/v1/auth/register", json=self.payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Email already registered"})
        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_registration_failure_rolls_back_without_commit(self) -> None:
        with patch("app.api.routes.auth.register_user", side_effect=RuntimeError("provisioning failed")):
            with self.assertRaises(RuntimeError):
                self.client.post("/api/v1/auth/register", json=self.payload)

        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_profile_update_changes_target_fields_and_timezone(self) -> None:
        user = self.make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        with patch("app.api.routes.auth.update_user_profile", return_value=user) as update_mock:
            response = self.client.patch(
                "/api/v1/auth/me",
                json={"first_name": "Augusta", "timezone": "Europe/London"},
            )

        self.assertEqual(response.status_code, 200)
        update_input = update_mock.call_args.kwargs["user_in"]
        self.assertEqual(update_input.first_name, "Augusta")
        self.assertEqual(update_input.timezone, "Europe/London")
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(user)

    def test_profile_update_rejects_invalid_timezone_without_writes(self) -> None:
        app.dependency_overrides[get_current_user] = self.make_user

        response = self.client.patch(
            "/api/v1/auth/me",
            json={"timezone": "Lima/Not-A-Timezone"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("valid IANA identifier", response.text)
        self.db.commit.assert_not_called()
        self.db.flush.assert_not_called()

    def test_registration_rejects_obsolete_fields(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={**self.payload, "username": "ada"},
        )

        self.assertEqual(response.status_code, 422)

    def test_stage_five_routes_remain_coherent(self) -> None:
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/workspaces").status_code, 404)
        self.assertEqual(self.client.post("/auth/register", json={}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
