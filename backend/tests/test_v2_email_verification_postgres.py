import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import (
    AccountActionToken,
    User,
    UserAccountStateEvent,
    Workspace,
    WorkspaceMember,
)
from app.models.enums import (
    AccountActionTokenType,
    AccountStatus,
    GlobalRole,
    WorkspaceKind,
)
from app.schemas.v2_identity import RegistrationRequestCreate
from app.services.email_delivery import RecordingEmailDelivery, VerificationEmail
from app.services.email_verification_service import (
    InvalidEmailVerificationTokenError,
    create_registration_with_verification,
    digest_action_token,
    resend_email_verification,
    verify_email_token,
)
from app.services.v2_identity import approve_registration_request


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("V2 email verification tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("V2 email verification tests require an allowlisted database")
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


def _registration() -> RegistrationRequestCreate:
    return RegistrationRequestCreate(
        email=f"verification-{uuid.uuid4()}@example.com",
        password="fixture password",
        first_name="Pending",
        last_name="Person",
    )


def _admin(db: Session) -> User:
    existing = db.scalar(
        sa.select(User).where(User.global_role == GlobalRole.GLOBAL_ADMIN)
    )
    if existing is not None:
        return existing
    now = datetime.now(timezone.utc)
    admin = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4()}@example.com",
        hashed_password="fixture-hash",
        first_name="Global",
        last_name="Admin",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN,
        email_verified_at=now,
        status_changed_at=now,
    )
    db.add(admin)
    db.flush()
    return admin


def _workspace_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        sa.select(sa.func.count())
        .select_from(Workspace)
        .where(
            Workspace.owner_user_id == user_id,
            Workspace.kind == WorkspaceKind.PERSONAL,
        )
    )


def test_complete_verification_then_approval_lifecycle(db: Session) -> None:
    delivery = RecordingEmailDelivery()
    issued = create_registration_with_verification(
        db,
        registration_in=_registration(),
    )
    delivery.send_verification_email(
        VerificationEmail(recipient=issued.recipient, raw_token=issued.raw_token)
    )
    user = db.scalar(sa.select(User).where(User.email == issued.recipient))
    assert user is not None
    token = db.scalar(
        sa.select(AccountActionToken).where(AccountActionToken.user_id == user.id)
    )
    assert token is not None
    assert token.token_digest == digest_action_token(issued.raw_token)
    assert issued.raw_token.encode() not in token.token_digest
    assert len(token.token_digest) == 32
    assert delivery.messages[0].raw_token == issued.raw_token
    assert _workspace_count(db, user.id) == 0

    verify_email_token(db, raw_token=issued.raw_token)
    db.flush()
    assert user.account_status == AccountStatus.PENDING_APPROVAL
    assert user.email_verified_at is not None
    assert token.consumed_at is not None
    assert _workspace_count(db, user.id) == 0
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(UserAccountStateEvent)
        .where(UserAccountStateEvent.user_id == user.id)
    ) == 2
    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=issued.raw_token)

    admin = _admin(db)
    approve_registration_request(db, user_id=user.id, actor=admin)
    db.flush()
    assert user.account_status == AccountStatus.ACTIVE
    assert _workspace_count(db, user.id) == 1
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
    ) == 1


def test_resend_revokes_old_token_and_only_new_token_verifies(db: Session) -> None:
    first = create_registration_with_verification(
        db,
        registration_in=_registration(),
    )
    second = resend_email_verification(db, email=first.recipient.upper())
    assert second is not None
    assert second.raw_token != first.raw_token

    first_token = db.scalar(
        sa.select(AccountActionToken).where(
            AccountActionToken.token_digest == digest_action_token(first.raw_token)
        )
    )
    assert first_token is not None
    assert first_token.revoked_at is not None
    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=first.raw_token)
    user = verify_email_token(db, raw_token=second.raw_token)
    assert user.account_status == AccountStatus.PENDING_APPROVAL


def test_password_reset_token_cannot_verify_email(db: Session) -> None:
    issued = create_registration_with_verification(
        db,
        registration_in=_registration(),
    )
    user = db.scalar(sa.select(User).where(User.email == issued.recipient))
    assert user is not None
    raw_reset_token = "B" * 43
    db.add(
        AccountActionToken(
            user_id=user.id,
            token_type=AccountActionTokenType.PASSWORD_RESET,
            token_digest=digest_action_token(raw_reset_token),
            expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.flush()
    with pytest.raises(InvalidEmailVerificationTokenError):
        verify_email_token(db, raw_token=raw_reset_token)
    assert user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION


def test_event_insert_failure_rolls_back_verification(db: Session) -> None:
    issued = create_registration_with_verification(
        db,
        registration_in=_registration(),
    )
    user = db.scalar(sa.select(User).where(User.email == issued.recipient))
    token = db.scalar(
        sa.select(AccountActionToken).where(AccountActionToken.user_id == user.id)
    )
    assert user is not None and token is not None

    def fail_transition_event(_mapper, _connection, event_row):
        if event_row.from_status == AccountStatus.PENDING_EMAIL_VERIFICATION:
            raise RuntimeError("forced event failure")

    savepoint = db.begin_nested()
    event.listen(UserAccountStateEvent, "before_insert", fail_transition_event)
    try:
        with pytest.raises(RuntimeError, match="forced event failure"):
            verify_email_token(db, raw_token=issued.raw_token)
    finally:
        event.remove(UserAccountStateEvent, "before_insert", fail_transition_event)
        savepoint.rollback()
    db.expire_all()

    restored_user = db.get(User, user.id)
    restored_token = db.get(AccountActionToken, token.id)
    assert restored_user is not None and restored_token is not None
    assert restored_user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert restored_user.email_verified_at is None
    assert restored_token.consumed_at is None
    assert restored_token.revoked_at is None


def test_two_concurrent_verifications_allow_exactly_one(engine) -> None:
    with Session(engine) as setup:
        issued = create_registration_with_verification(
            setup,
            registration_in=_registration(),
        )
        user = setup.scalar(sa.select(User).where(User.email == issued.recipient))
        assert user is not None
        user_id = user.id
        setup.commit()

    barrier = threading.Barrier(2)

    def verify_once() -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                verify_email_token(session, raw_token=issued.raw_token)
                session.commit()
                return "verified"
            except InvalidEmailVerificationTokenError:
                session.rollback()
                return "invalid"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(verify_once) for _ in range(2)]
        results = sorted(future.result() for future in futures)

    assert results == ["invalid", "verified"]
    with Session(engine) as verify:
        user = verify.get(User, user_id)
        assert user is not None
        assert user.account_status == AccountStatus.PENDING_APPROVAL
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(UserAccountStateEvent)
            .where(
                UserAccountStateEvent.user_id == user_id,
                UserAccountStateEvent.to_status == AccountStatus.PENDING_APPROVAL,
            )
        ) == 1
