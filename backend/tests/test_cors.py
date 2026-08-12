import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import User


class CorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

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
            is_active=True,
            is_verified=False,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def preflight(self, origin: str):
        return self.client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

    def test_localhost_vite_preflight_succeeds(self) -> None:
        response = self.preflight("http://localhost:5173")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])
        self.assertIn(
            "Authorization",
            response.headers["Access-Control-Allow-Headers"],
        )
        self.assertIn(
            "Content-Type",
            response.headers["Access-Control-Allow-Headers"],
        )

    def test_loopback_vite_preflight_succeeds(self) -> None:
        response = self.preflight("http://127.0.0.1:5173")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://127.0.0.1:5173",
        )

    def test_allowed_origin_is_returned_on_normal_response(self) -> None:
        response = self.client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

    def test_unknown_origin_is_not_granted_cors_access(self) -> None:
        response = self.preflight("http://malicious.example")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_versioned_login_behavior_is_unchanged(self) -> None:
        user = self.make_user()

        with patch("app.api.routes.auth.authenticate_user", return_value=user):
            response = self.client.post(
                "/api/v1/auth/login",
                headers={"Origin": "http://localhost:5173"},
                json={"email": "ada@example.com", "password": "plain-secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertIsInstance(response.json()["access_token"], str)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

    def test_authenticated_user_behavior_is_unchanged(self) -> None:
        user = self.make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Origin": "http://localhost:5173"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(user.id))
        self.assertEqual(response.json()["email"], user.email)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        self.db.add.assert_not_called()
        self.db.delete.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
