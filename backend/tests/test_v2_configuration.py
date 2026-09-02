import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db
from app.main import app
from app.models.enums import AccountStatus
from app.core.security import hash_password, verify_password
from app.schemas.v2_configuration import PasswordChange, ProfileUpdate
from app.services.v2_configuration import (
    CurrentPasswordIncorrectError,
    ProfileConflictError,
    change_password,
    update_profile,
)


NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
PASSWORD_HASH = hash_password("CurrentPassword!")


def _account(**changes: object) -> SimpleNamespace:
    values = {
        "id": uuid.uuid4(), "email": "ada@example.com", "first_name": "Ada",
        "last_name": "Lovelace", "timezone": "America/Lima",
        "account_status": AccountStatus.ACTIVE, "global_role": None,
        "lock_version": 3, "hashed_password": PASSWORD_HASH,
        "created_at": NOW, "updated_at": NOW,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _client(db: MagicMock, account: SimpleNamespace | None = None) -> TestClient:
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    if account is not None:
        app.dependency_overrides[get_current_account] = lambda: account
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_profile_read_is_own_minimized_account_and_read_only() -> None:
    db, account = MagicMock(), _account()
    with _client(db, account) as client:
        response = client.get("/api/v2/configuration/profile")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(account.id), "email": account.email, "first_name": "Ada",
        "last_name": "Lovelace", "timezone": "America/Lima", "lock_version": 3,
    }
    assert "global_role" not in response.text and "account_status" not in response.text
    db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()


def test_profile_update_commits_once_and_rejects_mass_assignment() -> None:
    db, account = MagicMock(), _account()
    updated = _account(id=account.id, first_name="Augusta", timezone="Europe/London", lock_version=4)
    payload = {"first_name": "Augusta", "last_name": "Lovelace", "timezone": "Europe/London", "lock_version": 3}
    with patch("app.api.v2.configuration.update_profile", return_value=updated) as service, _client(db, account) as client:
        response = client.patch("/api/v2/configuration/profile", json=payload)
    assert response.status_code == 200
    assert service.call_args.kwargs["account_id"] == account.id
    assert service.call_args.kwargs["profile_in"].model_dump() == payload
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(updated); db.rollback.assert_not_called()

    with patch("app.api.v2.configuration.update_profile") as service, _client(db, account) as client:
        invalid = client.patch("/api/v2/configuration/profile", json={**payload, "email": "other@example.com", "global_role": "GLOBAL_ADMIN"})
    assert invalid.status_code == 422
    service.assert_not_called()


@pytest.mark.parametrize("timezone_name", ["Not/A-Timezone", "", " America/Lima\x00"])
def test_profile_rejects_invalid_timezones(timezone_name: str) -> None:
    db, account = MagicMock(), _account()
    with _client(db, account) as client:
        response = client.patch("/api/v2/configuration/profile", json={"first_name": "Ada", "last_name": "Lovelace", "timezone": timezone_name, "lock_version": 3})
    assert response.status_code == 422
    db.commit.assert_not_called()


def test_profile_conflict_rolls_back_and_hides_detail() -> None:
    db, account = MagicMock(), _account()
    payload = {"first_name": "Ada", "last_name": "Lovelace", "timezone": "America/Lima", "lock_version": 2}
    with patch("app.api.v2.configuration.update_profile", side_effect=ProfileConflictError("private")), _client(db, account) as client:
        response = client.patch("/api/v2/configuration/profile", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROFILE_CONFLICT"
    assert "private" not in response.text
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_profile_service_locks_own_active_account_and_flushes_without_transaction_ownership() -> None:
    db, account = MagicMock(), _account()
    db.scalar.return_value = account
    result = update_profile(db, account_id=account.id, profile_in=ProfileUpdate(first_name="  Augusta  ", last_name=" King ", timezone="Europe/London", lock_version=3))
    assert result is account
    assert (account.first_name, account.last_name, account.timezone, account.lock_version) == ("Augusta", "King", "Europe/London", 4)
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    db.flush.assert_called_once_with(); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_profile_service_rejects_stale_or_inactive_before_flush() -> None:
    for account in (_account(lock_version=4), _account(account_status=AccountStatus.DISABLED)):
        db = MagicMock(); db.scalar.return_value = account
        with pytest.raises(ProfileConflictError):
            update_profile(db, account_id=account.id, profile_in=ProfileUpdate(first_name="Ada", last_name="Lovelace", timezone="America/Lima", lock_version=3))
        db.flush.assert_not_called()


def test_timezones_are_authenticated_sorted_and_read_only() -> None:
    db, account = MagicMock(), _account()
    with patch("app.api.v2.configuration.available_timezones", return_value={"UTC", "America/Lima"}), _client(db, account) as client:
        response = client.get("/api/v2/configuration/timezones")
    assert response.status_code == 200
    assert response.json() == {"items": ["America/Lima", "UTC"]}
    db.commit.assert_not_called(); db.flush.assert_not_called(); db.rollback.assert_not_called()


def test_configuration_requires_authentication_and_openapi_has_no_language_setting() -> None:
    db = MagicMock()
    with _client(db) as client:
        assert client.get("/api/v2/configuration/profile").status_code == 401
        assert client.get("/api/v2/configuration/timezones").status_code == 401
        assert client.post("/api/v2/configuration/password", json={"current_password": "CurrentPassword!", "new_password": "NewPassword!"}).status_code == 401
    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["ProfileUpdate"]["properties"]) == {"first_name", "last_name", "timezone", "lock_version"}
    assert "language" not in str(schemas).lower() and "locale" not in str(schemas).lower()


def test_password_change_commits_once_and_uses_only_authenticated_account() -> None:
    db, account = MagicMock(), _account()
    payload = {"current_password": "CurrentPassword!", "new_password": "NewPassword!"}
    with (
        patch("app.api.v2.configuration.enforce_rate_limit") as rate_limit,
        patch("app.api.v2.configuration.change_password", return_value=account) as service,
        _client(db, account) as client,
    ):
        response = client.post("/api/v2/configuration/password", json=payload)
    assert response.status_code == 204 and response.content == b""
    assert service.call_args.kwargs["account_id"] == account.id
    assert service.call_args.kwargs["password_in"].model_dump() == payload
    assert rate_limit.call_args.kwargs["actor_id"] == account.id
    db.commit.assert_called_once_with(); db.rollback.assert_not_called()


def test_password_change_rejects_wrong_current_password_and_mass_assignment() -> None:
    db, account = MagicMock(), _account()
    payload = {"current_password": "WrongPassword!", "new_password": "NewPassword!"}
    with (
        patch("app.api.v2.configuration.enforce_rate_limit"),
        patch("app.api.v2.configuration.change_password", side_effect=CurrentPasswordIncorrectError("private")) as service,
        _client(db, account) as client,
    ):
        response = client.post("/api/v2/configuration/password", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CURRENT_PASSWORD_INCORRECT"
    assert "private" not in response.text
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()

    with patch("app.api.v2.configuration.change_password") as service, _client(db, account) as client:
        invalid = client.post("/api/v2/configuration/password", json={**payload, "user_id": str(uuid.uuid4()), "global_role": "GLOBAL_ADMIN"})
    assert invalid.status_code == 422
    service.assert_not_called()


def test_password_service_locks_active_account_hashes_and_invalidates_old_secret() -> None:
    db, account = MagicMock(), _account()
    db.scalar.return_value = account
    result = change_password(
        db,
        account_id=account.id,
        password_in=PasswordChange(
            current_password="CurrentPassword!",
            new_password="NewPassword!",
        ),
    )
    assert result is account
    assert account.hashed_password not in {"CurrentPassword!", "NewPassword!", PASSWORD_HASH}
    assert verify_password("NewPassword!", account.hashed_password)
    assert not verify_password("CurrentPassword!", account.hashed_password)
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    db.flush.assert_called_once_with(); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_password_service_rejects_wrong_current_or_inactive_before_flush() -> None:
    for account, current in (
        (_account(), "WrongPassword!"),
        (_account(account_status=AccountStatus.DISABLED), "CurrentPassword!"),
    ):
        db = MagicMock(); db.scalar.return_value = account
        error = CurrentPasswordIncorrectError if account.account_status == AccountStatus.ACTIVE else ProfileConflictError
        with pytest.raises(error):
            change_password(db, account_id=account.id, password_in=PasswordChange(current_password=current, new_password="NewPassword!"))
        db.flush.assert_not_called()


def test_password_schema_reuses_policy_and_openapi_exposes_no_secret_response() -> None:
    with pytest.raises(ValueError):
        PasswordChange(current_password="CurrentPassword!", new_password="too-short")
    schema = app.openapi()["components"]["schemas"]["PasswordChange"]
    assert set(schema["properties"]) == {"current_password", "new_password"}
    operation = app.openapi()["paths"]["/api/v2/configuration/password"]["post"]
    assert "204" in operation["responses"]
