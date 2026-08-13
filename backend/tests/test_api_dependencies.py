import unittest
import uuid

from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import User, Workspace, WorkspaceKind


class ApiDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.user_id = uuid.uuid4()
        self.user = User(id=self.user_id, is_active=True)

    def assert_credentials_error(self, context: unittest.case._AssertRaisesContext) -> None:
        error = context.exception
        self.assertEqual(error.status_code, 401)
        self.assertEqual(error.detail, "Could not validate credentials")
        self.assertEqual(error.headers, {"WWW-Authenticate": "Bearer"})

    @patch("app.api.dependencies.decode_access_token")
    def test_valid_token_returns_matching_user(self, decode_mock: MagicMock) -> None:
        decode_mock.return_value = str(self.user_id)
        self.db.scalar.return_value = self.user

        result = get_current_user("token", self.db)

        self.assertIs(result, self.user)

    @patch("app.api.dependencies.decode_access_token")
    def test_subject_is_converted_to_uuid_before_lookup(
        self,
        decode_mock: MagicMock,
    ) -> None:
        decode_mock.return_value = str(self.user_id)
        self.db.scalar.return_value = self.user

        get_current_user("token", self.db)

        statement = self.db.scalar.call_args.args[0]
        parameter_values = statement.compile().params.values()
        self.assertIn(self.user_id, parameter_values)
        self.assertNotIn(str(self.user_id), parameter_values)

    @patch("app.api.dependencies.decode_access_token", return_value=None)
    def test_malformed_or_invalid_token_returns_unauthorized(
        self,
        _decode_mock: MagicMock,
    ) -> None:
        with self.assertRaises(HTTPException) as context:
            get_current_user("malformed-token", self.db)

        self.assert_credentials_error(context)
        self.db.scalar.assert_not_called()

    @patch("app.api.dependencies.decode_access_token", return_value=None)
    def test_expired_token_returns_unauthorized(
        self,
        _decode_mock: MagicMock,
    ) -> None:
        with self.assertRaises(HTTPException) as context:
            get_current_user("expired-token", self.db)

        self.assert_credentials_error(context)

    @patch("app.api.dependencies.decode_access_token", return_value="not-a-uuid")
    def test_non_uuid_subject_returns_unauthorized(
        self,
        _decode_mock: MagicMock,
    ) -> None:
        with self.assertRaises(HTTPException) as context:
            get_current_user("token", self.db)

        self.assert_credentials_error(context)
        self.db.scalar.assert_not_called()

    @patch("app.api.dependencies.decode_access_token")
    def test_missing_user_returns_unauthorized(self, decode_mock: MagicMock) -> None:
        decode_mock.return_value = str(self.user_id)
        self.db.scalar.return_value = None

        with self.assertRaises(HTTPException) as context:
            get_current_user("token", self.db)

        self.assert_credentials_error(context)

    @patch("app.api.dependencies.decode_access_token")
    def test_inactive_user_returns_unauthorized(self, decode_mock: MagicMock) -> None:
        decode_mock.return_value = str(self.user_id)
        self.db.scalar.return_value = User(id=self.user_id, is_active=False)

        with self.assertRaises(HTTPException) as context:
            get_current_user("token", self.db)

        self.assert_credentials_error(context)

    @patch("app.api.dependencies.decode_access_token")
    def test_current_user_lookup_never_writes_session(
        self,
        decode_mock: MagicMock,
    ) -> None:
        decode_mock.return_value = str(self.user_id)
        self.db.scalar.return_value = self.user

        get_current_user("token", self.db)

        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.refresh.assert_not_called()
        self.db.rollback.assert_not_called()
        self.db.delete.assert_not_called()

    def test_routes_and_shared_database_override_remain_available(self) -> None:
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        try:
            with patch(
                "app.api.routes.auth.authenticate_user",
                return_value=None,
            ) as authenticate_mock:
                login_response = client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "ada@example.com",
                        "password": "plain-secret",
                    },
                )

            self.assertEqual(login_response.status_code, 401)
            authenticate_mock.assert_called_once_with(
                self.db,
                email="ada@example.com",
                password="plain-secret",
            )
            self.assertEqual(client.post("/api/v1/auth/register", json={}).status_code, 422)
            self.assertEqual(client.get("/api/v1/workspaces").status_code, 404)
        finally:
            client.close()
            app.dependency_overrides.clear()

    def test_personal_workspace_resolver_returns_exact_owner_workspace(self) -> None:
        workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
        self.db.scalars.return_value.all.return_value = [workspace]

        result = get_personal_workspace(self.user, self.db)

        self.assertIs(result, workspace)
        statement = self.db.scalars.call_args.args[0]
        parameters = set(statement.compile().params.values())
        self.assertIn(self.user_id, parameters)
        self.assertIn(WorkspaceKind.PERSONAL, parameters)

    def test_personal_workspace_resolver_rejects_no_match(self) -> None:
        self.db.scalars.return_value.all.return_value = []

        with self.assertRaises(HTTPException) as context:
            get_personal_workspace(self.user, self.db)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "Personal workspace invariant violated")

    def test_personal_workspace_resolver_rejects_multiple_matches(self) -> None:
        self.db.scalars.return_value.all.return_value = [
            Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL),
            Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL),
        ]

        with self.assertRaises(HTTPException) as context:
            get_personal_workspace(self.user, self.db)

        self.assertEqual(context.exception.status_code, 409)

    def test_personal_workspace_resolver_is_read_only(self) -> None:
        self.db.scalars.return_value.all.return_value = [
            Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
        ]

        get_personal_workspace(self.user, self.db)

        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.rollback.assert_not_called()
        self.db.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
