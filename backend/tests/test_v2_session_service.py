import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import User
from app.models.enums import AccountStatus
from app.services.session_service import InvalidCredentialsError, authenticate_session


NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _user(status: AccountStatus = AccountStatus.ACTIVE) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        hashed_password="old-valid-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        email_verified_at=NOW,
        status_changed_at=NOW,
    )


def test_success_normalizes_email_and_persists_rehash_only_when_needed() -> None:
    db = MagicMock()
    user = _user()
    db.scalar.return_value = user
    with patch(
        "app.services.session_service.verify_and_update_password",
        return_value=(True, "current-hash"),
    ) as verify:
        assert authenticate_session(
            db,
            email=" Person@Example.com ",
            password="ValidPassword!",
        ) is user
    verify.assert_called_once_with("ValidPassword!", "old-valid-hash")
    assert user.hashed_password == "current-hash"
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_unknown_account_uses_dummy_hash_and_is_neutral() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with patch(
        "app.services.session_service.verify_and_update_password",
        return_value=(False, None),
    ) as verify:
        with pytest.raises(InvalidCredentialsError):
            authenticate_session(
                db,
                email="unknown@example.com",
                password="WrongPassword!",
            )
    assert verify.call_args.args[0] == "WrongPassword!"
    assert verify.call_args.args[1].startswith("$argon2")
    db.flush.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.PENDING_APPROVAL,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ],
)
def test_nonactive_and_wrong_password_share_failure(status: AccountStatus) -> None:
    db = MagicMock()
    db.scalar.return_value = _user(status)
    with patch(
        "app.services.session_service.verify_and_update_password",
        return_value=(True, "must-not-be-persisted"),
    ):
        with pytest.raises(InvalidCredentialsError):
            authenticate_session(
                db,
                email="person@example.com",
                password="ValidPassword!",
            )
    db.flush.assert_not_called()
