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
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": user.updated_at.isoformat().replace("+00:00", "Z"),
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

    def test_stage_four_routes_remain_coherent(self) -> None:
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/workspaces").status_code, 404)
        self.assertEqual(self.client.post("/auth/register", json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
