import hashlib
import uuid

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models import AccountActionToken, User
from app.models.enums import AccountActionTokenType, AccountStatus
from app.services.account_action_token_service import ACTION_TOKEN_BYTES
from app.services.email_delivery import (
    PasswordResetEmail,
    RecordingEmailDelivery,
    build_password_reset_url,
)
from app.services.password_recovery_service import (
    PASSWORD_RESET_TOKEN_LENGTH,
    PASSWORD_RESET_TOKEN_TTL,
    InvalidPasswordResetTokenError,
    issue_password_reset_token,
    request_password_recovery,
    reset_password,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
RAW_TOKEN = "R" * PASSWORD_RESET_TOKEN_LENGTH


def _user(status: AccountStatus = AccountStatus.ACTIVE) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        hashed_password="old-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        email_verified_at=(
            None if status is AccountStatus.PENDING_EMAIL_VERIFICATION else NOW
        ),
        status_changed_at=NOW,
        lock_version=1,
    )


def _token(user: User, **changes: object) -> AccountActionToken:
    values = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "token_type": AccountActionTokenType.PASSWORD_RESET,
        "token_digest": hashlib.sha256(RAW_TOKEN.encode("ascii")).digest(),
        "expires_at": NOW + timedelta(minutes=30),
        "consumed_at": None,
        "revoked_at": None,
        "created_at": NOW - timedelta(minutes=1),
    }
    values.update(changes)
    return AccountActionToken(**values)


def test_reset_token_uses_shared_entropy_digest_and_shorter_ttl() -> None:
    db = MagicMock()
    user = _user()
    with patch(
        "app.services.account_action_token_service.secrets.token_urlsafe",
        return_value=RAW_TOKEN,
    ) as generator:
        issued = issue_password_reset_token(db, user=user, now=NOW)

    generator.assert_called_once_with(ACTION_TOKEN_BYTES)
    assert issued.expires_at == NOW + PASSWORD_RESET_TOKEN_TTL
    assert PASSWORD_RESET_TOKEN_TTL < timedelta(hours=24)
    token = db.add.call_args.args[0]
    assert token.token_type == AccountActionTokenType.PASSWORD_RESET
    assert token.token_digest == hashlib.sha256(RAW_TOKEN.encode()).digest()
    assert not hasattr(token, "raw_token")
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_recovery_normalizes_email_revokes_previous_and_issues_new() -> None:
    db = MagicMock()
    user = _user()
    previous = _token(user)
    db.scalar.side_effect = [user.id, user]
    db.scalars.return_value.all.return_value = [previous]
    with patch(
        "app.services.account_action_token_service.secrets.token_urlsafe",
        return_value=RAW_TOKEN,
    ):
        issued = request_password_recovery(db, email=" Person@Example.com ")

    assert issued is not None
    assert issued.recipient == "person@example.com"
    assert previous.revoked_at is not None
    assert db.flush.call_count == 2
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "existing",
    [
        None,
        _user(AccountStatus.PENDING_EMAIL_VERIFICATION),
        _user(AccountStatus.PENDING_APPROVAL),
        _user(AccountStatus.REJECTED),
        _user(AccountStatus.DISABLED),
    ],
)
def test_recovery_is_neutral_and_does_not_issue_for_ineligible_accounts(
    existing: User | None,
) -> None:
    db = MagicMock()
    db.scalar.side_effect = [None] if existing is None else [existing.id, existing]
    db.scalars.return_value.all.return_value = []
    assert request_password_recovery(db, email="person@example.com") is None
    db.add.assert_not_called()


def test_reset_hashes_password_consumes_token_and_calls_session_hook() -> None:
    db = MagicMock()
    user = _user()
    token = _token(user)
    db.execute.return_value.one_or_none.return_value = SimpleNamespace(
        id=token.id,
        user_id=user.id,
    )
    db.scalar.side_effect = [token, user]
    hook = MagicMock()
    with patch(
        "app.services.password_recovery_service.hash_password",
        return_value="new-hash",
    ) as hasher:
        result = reset_password(
            db,
            raw_token=RAW_TOKEN,
            new_password="new password",
            now=NOW,
            session_invalidation_hook=hook,
        )

    assert result is user
    hasher.assert_called_once_with("new password")
    assert user.hashed_password == "new-hash"
    assert user.account_status == AccountStatus.ACTIVE
    assert token.consumed_at == NOW
    assert token.revoked_at is None
    hook.assert_called_once_with(db, user)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": NOW},
        {"consumed_at": NOW - timedelta(seconds=1)},
        {"revoked_at": NOW - timedelta(seconds=1)},
        {"token_type": AccountActionTokenType.EMAIL_VERIFICATION},
    ],
)
def test_expired_consumed_revoked_or_wrong_purpose_is_neutral(
    changes: dict[str, object],
) -> None:
    db = MagicMock()
    user = _user()
    token = _token(user, **changes)
    db.execute.return_value.one_or_none.return_value = SimpleNamespace(
        id=token.id,
        user_id=user.id,
    )
    db.scalar.side_effect = [token, user]
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            db,
            raw_token=RAW_TOKEN,
            new_password="new password",
            now=NOW,
        )
    assert user.hashed_password == "old-hash"
    db.flush.assert_not_called()


@pytest.mark.parametrize(
    "raw_token",
    ["invalid", "!" * 43, "R" * 42, "R" * 44, "N" * 43],
)
def test_malformed_or_unknown_reset_token_is_neutral(raw_token: str) -> None:
    db = MagicMock()
    if raw_token == "N" * 43:
        db.execute.return_value.one_or_none.return_value = None
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(db, raw_token=raw_token, new_password="new password", now=NOW)
    db.scalar.assert_not_called()
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
def test_ineligible_account_cannot_reset_or_change_state(
    status: AccountStatus,
) -> None:
    db = MagicMock()
    user = _user(status)
    token = _token(user)
    db.execute.return_value.one_or_none.return_value = SimpleNamespace(
        id=token.id,
        user_id=user.id,
    )
    db.scalar.side_effect = [token, user]
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(db, raw_token=RAW_TOKEN, new_password="new password", now=NOW)
    assert user.account_status == status
    assert user.hashed_password == "old-hash"


def test_recording_delivery_and_reset_url_are_provider_neutral() -> None:
    delivery = RecordingEmailDelivery()
    message = PasswordResetEmail(
        recipient="person@example.com",
        raw_token=RAW_TOKEN,
    )
    delivery.send_password_reset_email(message)
    assert delivery.messages == [message]
    url = build_password_reset_url(
        frontend_base_url="https://app.example.com/",
        raw_token=RAW_TOKEN,
    )
    assert url == f"https://app.example.com/restablecer-contrasena?token={RAW_TOKEN}"
    assert "person@example.com" not in url
