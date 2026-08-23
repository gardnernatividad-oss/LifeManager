import hashlib
import uuid

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models import AccountActionToken, User, UserAccountStateEvent
from app.models.enums import AccountActionTokenType, AccountStatus
from app.services.email_delivery import (
    RecordingEmailDelivery,
    VerificationEmail,
    build_verification_url,
)
from app.services.email_verification_service import (
    EMAIL_VERIFICATION_TOKEN_BYTES,
    EMAIL_VERIFICATION_TOKEN_LENGTH,
    EMAIL_VERIFICATION_TOKEN_TTL,
    InvalidEmailVerificationTokenError,
    digest_action_token,
    issue_email_verification_token,
    resend_email_verification,
    verify_email_token,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
RAW_TOKEN = "A" * EMAIL_VERIFICATION_TOKEN_LENGTH


def _user(
    status: AccountStatus = AccountStatus.PENDING_EMAIL_VERIFICATION,
) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        hashed_password="fixture-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        email_verified_at=None,
        status_changed_at=NOW,
        lock_version=1,
    )


def _token(user: User, **changes: object) -> AccountActionToken:
    values = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "token_type": AccountActionTokenType.EMAIL_VERIFICATION,
        "token_digest": digest_action_token(RAW_TOKEN),
        "expires_at": NOW + timedelta(hours=1),
        "consumed_at": None,
        "revoked_at": None,
        "created_at": NOW - timedelta(hours=1),
    }
    values.update(changes)
    return AccountActionToken(**values)


def test_token_generation_uses_32_random_bytes_and_sha256_digest() -> None:
    db = MagicMock()
    user = _user()
    with patch(
        "app.services.email_verification_service.secrets.token_urlsafe",
        return_value=RAW_TOKEN,
    ) as generator:
        issued = issue_email_verification_token(db, user=user, now=NOW)

    generator.assert_called_once_with(EMAIL_VERIFICATION_TOKEN_BYTES)
    assert len(issued.raw_token) == EMAIL_VERIFICATION_TOKEN_LENGTH
    assert issued.expires_at == NOW + EMAIL_VERIFICATION_TOKEN_TTL
    persisted = db.add.call_args.args[0]
    assert isinstance(persisted, AccountActionToken)
    assert persisted.token_digest == hashlib.sha256(RAW_TOKEN.encode("ascii")).digest()
    assert not hasattr(persisted, "raw_token")
    assert persisted.token_type == AccountActionTokenType.EMAIL_VERIFICATION
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_verification_transitions_consumes_and_revokes_other_tokens() -> None:
    db = MagicMock()
    user = _user()
    token = _token(user)
    db.execute.return_value.one_or_none.return_value = SimpleNamespace(
        id=token.id,
        user_id=user.id,
    )
    db.scalar.side_effect = [token, user]

    result = verify_email_token(db, raw_token=RAW_TOKEN, now=NOW)

    assert result is user
    assert user.email_verified_at == NOW
    assert user.account_status == AccountStatus.PENDING_APPROVAL
    assert token.consumed_at == NOW
    assert token.revoked_at is None
    added = [call.args[0] for call in db.add.call_args_list]
    event = next(value for value in added if isinstance(value, UserAccountStateEvent))
    assert event.from_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert event.to_status == AccountStatus.PENDING_APPROVAL
    assert event.actor_user_id is None
    assert event.reason == "EMAIL_VERIFIED"
    assert db.execute.call_count == 2
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "token_changes",
    [
        {"expires_at": NOW},
        {"consumed_at": NOW - timedelta(minutes=1)},
        {"revoked_at": NOW - timedelta(minutes=1)},
        {"token_type": AccountActionTokenType.PASSWORD_RESET},
    ],
)
def test_expired_consumed_revoked_or_wrong_purpose_is_neutral(
    token_changes: dict[str, object],
) -> None:
    db = MagicMock()
    user = _user()
    token = _token(user, **token_changes)
    db.execute.return_value.one_or_none.return_value = SimpleNamespace(
        id=token.id,
        user_id=user.id,
    )
    db.scalar.side_effect = [token, user]

    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=RAW_TOKEN, now=NOW)

    assert user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    db.flush.assert_not_called()


@pytest.mark.parametrize(
    "raw_token",
    ["invalid", "!" * 43, "A" * 42, "A" * 44, "B" * 43],
)
def test_malformed_or_unknown_token_is_neutral(raw_token: str) -> None:
    db = MagicMock()
    if raw_token == "B" * 43:
        db.execute.return_value.one_or_none.return_value = None
    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=raw_token, now=NOW)
    db.scalar.assert_not_called()
    db.flush.assert_not_called()


def test_resend_normalizes_email_revokes_old_and_issues_new_token() -> None:
    db = MagicMock()
    user = _user()
    old_token = _token(user)
    db.scalar.side_effect = [user.id, user]
    db.scalars.return_value.all.return_value = [old_token]
    with patch(
        "app.services.email_verification_service.secrets.token_urlsafe",
        return_value=RAW_TOKEN,
    ):
        issued = resend_email_verification(
            db,
            email=" Person@Example.com ",
        )

    assert issued is not None
    lookup = str(db.scalar.call_args.args[0])
    assert "users.email" in lookup
    assert old_token.revoked_at is not None
    db.add.assert_called_once()
    assert db.flush.call_count == 2


def test_resend_is_neutral_for_missing_or_ineligible_account() -> None:
    for existing in (None, _user(AccountStatus.ACTIVE)):
        db = MagicMock()
        db.scalar.side_effect = (
            [None]
            if existing is None
            else [existing.id, existing]
        )
        db.scalars.return_value.all.return_value = []
        assert resend_email_verification(db, email="person@example.com") is None
        db.add.assert_not_called()
        db.flush.assert_not_called()


def test_recording_delivery_captures_without_external_send() -> None:
    delivery = RecordingEmailDelivery()
    message = VerificationEmail(
        recipient="person@example.com",
        raw_token=RAW_TOKEN,
    )
    delivery.send_verification_email(message)
    assert delivery.messages == [message]


def test_verification_url_contains_only_frontend_path_and_token() -> None:
    url = build_verification_url(
        frontend_base_url="https://app.example.com/",
        raw_token=RAW_TOKEN,
    )
    assert url == f"https://app.example.com/verificar-correo?token={RAW_TOKEN}"
    assert "person@example.com" not in url
