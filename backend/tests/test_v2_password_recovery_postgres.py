import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import AccountActionToken, User, UserAccountStateEvent, Workspace
from app.models.enums import AccountActionTokenType, AccountStatus
from app.services.email_delivery import PasswordResetEmail, RecordingEmailDelivery
from app.services.email_verification_service import (
    InvalidEmailVerificationTokenError,
    digest_action_token,
    issue_email_verification_token,
    verify_email_token,
)
from app.services.password_recovery_service import (
    InvalidPasswordResetTokenError,
    PasswordRecoveryIssuanceConflictError,
    request_password_recovery,
    reset_password,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("V2 password recovery tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("V2 password recovery tests require an allowlisted database")
    return url


@pytest.fixture
def engine():
    engine = sa.create_engine(_local_test_url())
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _active_user(db: Session, *, password: str = "old password") -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email=f"active-{uuid.uuid4()}@example.com",
        hashed_password=hash_password(password),
        first_name="Active",
        last_name="Person",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        email_verified_at=now,
        status_changed_at=now,
    )
    db.add(user)
    db.flush()
    return user


def _workspace_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        sa.select(sa.func.count())
        .select_from(Workspace)
        .where(Workspace.owner_user_id == user_id)
    )


def test_complete_password_recovery_lifecycle(db: Session) -> None:
    user = _active_user(db)
    original_hash = user.hashed_password
    original_status = user.account_status
    delivery = RecordingEmailDelivery()

    issued = request_password_recovery(db, email=user.email.upper())
    assert issued is not None
    delivery.send_password_reset_email(
        PasswordResetEmail(recipient=issued.recipient, raw_token=issued.raw_token)
    )
    token = db.scalar(
        sa.select(AccountActionToken).where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.token_type == AccountActionTokenType.PASSWORD_RESET,
        )
    )
    assert token is not None
    assert token.token_digest == digest_action_token(issued.raw_token)
    assert issued.raw_token.encode() not in token.token_digest
    assert len(token.token_digest) == 32
    assert delivery.messages[0].raw_token == issued.raw_token
    assert _workspace_count(db, user.id) == 0

    reset_password(
        db,
        raw_token=issued.raw_token,
        new_password="new password",
    )
    db.flush()
    assert user.hashed_password != original_hash
    assert not verify_password("old password", user.hashed_password)
    assert verify_password("new password", user.hashed_password)
    assert user.account_status == original_status == AccountStatus.ACTIVE
    assert token.consumed_at is not None
    assert _workspace_count(db, user.id) == 0
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(UserAccountStateEvent)
        .where(UserAccountStateEvent.user_id == user.id)
    ) == 0
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            db,
            raw_token=issued.raw_token,
            new_password="another password",
        )


def test_reissue_revokes_old_token_and_new_token_resets(db: Session) -> None:
    user = _active_user(db)
    first = request_password_recovery(db, email=user.email)
    second = request_password_recovery(db, email=user.email)
    assert first is not None and second is not None
    assert first.raw_token != second.raw_token

    first_token = db.scalar(
        sa.select(AccountActionToken).where(
            AccountActionToken.token_digest == digest_action_token(first.raw_token)
        )
    )
    assert first_token is not None
    assert first_token.revoked_at is not None
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(db, raw_token=first.raw_token, new_password="new password")
    reset_password(db, raw_token=second.raw_token, new_password="new password")
    assert verify_password("new password", user.hashed_password)


def test_token_purposes_are_bidirectionally_isolated(db: Session) -> None:
    active = _active_user(db)
    reset = request_password_recovery(db, email=active.email)
    assert reset is not None
    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=reset.raw_token)

    pending = User(
        id=uuid.uuid4(),
        email=f"pending-{uuid.uuid4()}@example.com",
        hashed_password="fixture-hash",
        first_name="Pending",
        last_name="Person",
        timezone="America/Lima",
        account_status=AccountStatus.PENDING_EMAIL_VERIFICATION,
        email_verified_at=None,
        status_changed_at=datetime.now(timezone.utc),
    )
    db.add(pending)
    db.flush()
    verification = issue_email_verification_token(db, user=pending)
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            db,
            raw_token=verification.raw_token,
            new_password="new password",
        )


def test_expired_and_revoked_tokens_are_rejected(db: Session) -> None:
    user = _active_user(db)
    issued = request_password_recovery(db, email=user.email)
    assert issued is not None
    token = db.scalar(
        sa.select(AccountActionToken).where(
            AccountActionToken.token_digest == digest_action_token(issued.raw_token)
        )
    )
    assert token is not None
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            db,
            raw_token=issued.raw_token,
            new_password="new password",
            now=token.expires_at,
        )

    token.revoked_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(db, raw_token=issued.raw_token, new_password="new password")


def test_token_update_failure_rolls_back_password_and_consumption(db: Session) -> None:
    user = _active_user(db)
    issued = request_password_recovery(db, email=user.email)
    assert issued is not None
    token = db.scalar(
        sa.select(AccountActionToken).where(
            AccountActionToken.token_digest == digest_action_token(issued.raw_token)
        )
    )
    assert token is not None
    original_hash = user.hashed_password

    def fail_consumption(_mapper, _connection, token_row):
        if token_row.consumed_at is not None:
            raise RuntimeError("forced token failure")

    savepoint = db.begin_nested()
    event.listen(AccountActionToken, "before_update", fail_consumption)
    try:
        with pytest.raises(RuntimeError, match="forced token failure"):
            reset_password(
                db,
                raw_token=issued.raw_token,
                new_password="new password",
            )
    finally:
        event.remove(AccountActionToken, "before_update", fail_consumption)
        savepoint.rollback()
    db.expire_all()

    restored_user = db.get(User, user.id)
    restored_token = db.get(AccountActionToken, token.id)
    assert restored_user is not None and restored_token is not None
    assert restored_user.hashed_password == original_hash
    assert restored_user.account_status == AccountStatus.ACTIVE
    assert restored_token.consumed_at is None
    assert restored_token.revoked_at is None


def test_two_concurrent_resets_allow_exactly_one(engine) -> None:
    with Session(engine) as setup:
        user = _active_user(setup)
        issued = request_password_recovery(setup, email=user.email)
        assert issued is not None
        user_id = user.id
        setup.commit()

    barrier = threading.Barrier(2)

    def reset_once(candidate: str) -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                reset_password(
                    session,
                    raw_token=issued.raw_token,
                    new_password=candidate,
                )
                session.commit()
                return "reset"
            except InvalidPasswordResetTokenError:
                session.rollback()
                return "invalid"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(reset_once, "first password"),
            pool.submit(reset_once, "second password"),
        ]
        results = sorted(future.result() for future in futures)
    assert results == ["invalid", "reset"]
    with Session(engine) as verify:
        user = verify.get(User, user_id)
        assert user is not None
        assert user.account_status == AccountStatus.ACTIVE
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(AccountActionToken)
            .where(
                AccountActionToken.user_id == user_id,
                AccountActionToken.token_type == AccountActionTokenType.PASSWORD_RESET,
                AccountActionToken.consumed_at.is_not(None),
            )
        ) == 1


def test_concurrent_recovery_leaves_one_active_token(engine) -> None:
    with Session(engine) as setup:
        user = _active_user(setup)
        user_id, email = user.id, user.email
        setup.commit()

    barrier = threading.Barrier(2)

    def issue_once() -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                issued = request_password_recovery(session, email=email)
                session.commit()
                return "issued" if issued is not None else "neutral"
            except PasswordRecoveryIssuanceConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(issue_once) for _ in range(2)]
        results = [future.result() for future in futures]
    assert all(result in {"issued", "conflict"} for result in results)
    assert "issued" in results
    with Session(engine) as verify:
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(AccountActionToken)
            .where(
                AccountActionToken.user_id == user_id,
                AccountActionToken.token_type == AccountActionTokenType.PASSWORD_RESET,
                AccountActionToken.consumed_at.is_(None),
                AccountActionToken.revoked_at.is_(None),
            )
        ) == 1
