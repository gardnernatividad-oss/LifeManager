import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import event

from app.models import User, UserAccountStateEvent, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, WorkspaceKind
from app.schemas.v2_identity import RegistrationRequestCreate
from app.services.v2_identity import (
    AccountStateConflictError,
    RegistrationRequestConflictError,
    approve_registration_request,
    create_registration_request,
    list_pending_registration_requests,
    reject_registration_request,
    transition_account_state,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("V2 identity integration tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("V2 identity integration tests require an allowlisted database")
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


def _approvable_registration(db: Session) -> User:
    user = create_registration_request(
        db,
        registration_in=RegistrationRequestCreate(
            email=f"registration-{uuid.uuid4()}@example.com",
            password="fixture password",
            first_name="Pending",
            last_name="Person",
        ),
    )
    assert user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert db.scalar(
        select_personal_workspace_count(user.id)
    ) == 0
    user.email_verified_at = datetime.now(timezone.utc)
    transition_account_state(
        db,
        user=user,
        new_status=AccountStatus.PENDING_APPROVAL,
        actor_user_id=None,
        reason="TEST_EMAIL_VERIFICATION",
    )
    db.flush()
    return user


def _new_registration(db: Session, *, email: str | None = None) -> User:
    return create_registration_request(
        db,
        registration_in=RegistrationRequestCreate(
            email=email or f"registration-{uuid.uuid4()}@example.com",
            password="fixture password",
            first_name="Pending",
            last_name="Person",
        ),
    )


def select_personal_workspace_count(user_id: uuid.UUID):
    return (
        sa.select(sa.func.count())
        .select_from(Workspace)
        .where(
            Workspace.owner_user_id == user_id,
            Workspace.kind == WorkspaceKind.PERSONAL,
        )
    )


def test_registration_normalization_duplicate_and_initial_absences(db: Session) -> None:
    user = _new_registration(db, email="  Case.User@Example.com ")
    db.flush()

    assert user.email == "case.user@example.com"
    assert user.hashed_password != "fixture password"
    assert user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert user.global_role is None
    assert user.email_verified_at is None
    assert db.scalar(select_personal_workspace_count(user.id)) == 0
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
    ) == 0
    events = list(
        db.scalars(
            sa.select(UserAccountStateEvent).where(
                UserAccountStateEvent.user_id == user.id
            )
        ).all()
    )
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert events[0].actor_user_id is None

    with pytest.raises(RegistrationRequestConflictError):
        _new_registration(db, email="case.user@example.com")
    with pytest.raises(RegistrationRequestConflictError):
        _new_registration(db, email=" CASE.USER@example.COM ")


@pytest.mark.parametrize(
    "existing_status",
    [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.PENDING_APPROVAL,
        AccountStatus.ACTIVE,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ],
)
def test_duplicate_registration_is_rejected_independently_of_account_state(
    db: Session,
    existing_status: AccountStatus,
) -> None:
    email = f"state-{existing_status.value.lower()}-{uuid.uuid4()}@example.com"
    existing = _new_registration(db, email=email)
    if existing_status is not AccountStatus.PENDING_EMAIL_VERIFICATION:
        existing.email_verified_at = datetime.now(timezone.utc)
        existing.account_status = existing_status
        existing.status_changed_at = datetime.now(timezone.utc)
    db.flush()

    with pytest.raises(RegistrationRequestConflictError):
        _new_registration(db, email=f" {email.upper()} ")


def test_pending_queue_contains_only_pending_approval(db: Session) -> None:
    pending_email = _new_registration(db)
    pending_approval = _approvable_registration(db)
    active = _approvable_registration(db)
    active.account_status = AccountStatus.ACTIVE
    rejected = _approvable_registration(db)
    rejected.account_status = AccountStatus.REJECTED
    disabled = _approvable_registration(db)
    disabled.account_status = AccountStatus.DISABLED
    db.flush()

    queued_ids = {user.id for user in list_pending_registration_requests(db)}
    assert pending_approval.id in queued_ids
    assert {
        pending_email.id,
        active.id,
        rejected.id,
        disabled.id,
    }.isdisjoint(queued_ids)


def test_registration_approval_is_atomic_and_double_approval_conflicts(db: Session) -> None:
    admin = _admin(db)
    user = _approvable_registration(db)

    approve_registration_request(db, user_id=user.id, actor=admin)
    db.flush()
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")

    assert user.account_status == AccountStatus.ACTIVE
    assert db.scalar(select_personal_workspace_count(user.id)) == 1
    workspace = db.scalar(
        sa.select(Workspace).where(Workspace.owner_user_id == user.id)
    )
    assert workspace is not None
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == "ACTIVE",
        )
    ) == 1
    transitions = list(
        db.scalars(
            sa.select(UserAccountStateEvent)
            .where(UserAccountStateEvent.user_id == user.id)
            .order_by(UserAccountStateEvent.created_at, UserAccountStateEvent.id)
        ).all()
    )
    assert [event.to_status for event in transitions] == [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.PENDING_APPROVAL,
        AccountStatus.ACTIVE,
    ]
    with pytest.raises(AccountStateConflictError):
        approve_registration_request(db, user_id=user.id, actor=admin)
    assert db.scalar(select_personal_workspace_count(user.id)) == 1


def test_rejection_creates_event_without_personal_workspace(db: Session) -> None:
    admin = _admin(db)
    user = _approvable_registration(db)

    reject_registration_request(
        db,
        user_id=user.id,
        actor=admin,
        reason="TEST_REJECTION",
    )
    db.flush()

    assert user.account_status == AccountStatus.REJECTED
    assert db.scalar(select_personal_workspace_count(user.id)) == 0
    final_event = db.scalar(
        sa.select(UserAccountStateEvent)
        .where(UserAccountStateEvent.user_id == user.id)
        .order_by(UserAccountStateEvent.created_at.desc(), UserAccountStateEvent.id.desc())
        .limit(1)
    )
    assert final_event is not None
    assert final_event.actor_user_id == admin.id
    assert final_event.to_status == AccountStatus.REJECTED


def test_global_admin_has_no_membership_in_another_users_personal_workspace(db: Session) -> None:
    admin = _admin(db)
    user = _approvable_registration(db)
    approve_registration_request(db, user_id=user.id, actor=admin)
    db.flush()

    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            Workspace.owner_user_id == user.id,
            WorkspaceMember.user_id == admin.id,
        )
    ) == 0


def test_membership_insert_failure_rolls_back_entire_approval(db: Session) -> None:
    admin = _admin(db)
    user = _approvable_registration(db)
    db.flush()
    original_event_count = db.scalar(
        sa.select(sa.func.count())
        .select_from(UserAccountStateEvent)
        .where(UserAccountStateEvent.user_id == user.id)
    )

    def fail_membership(*_args, **_kwargs):
        raise RuntimeError("forced membership failure")

    savepoint = db.begin_nested()
    event.listen(WorkspaceMember, "before_insert", fail_membership)
    try:
        with pytest.raises(RuntimeError, match="forced membership failure"):
            approve_registration_request(db, user_id=user.id, actor=admin)
    finally:
        event.remove(WorkspaceMember, "before_insert", fail_membership)
        savepoint.rollback()
    db.expire_all()

    restored = db.get(User, user.id)
    assert restored is not None
    assert restored.account_status == AccountStatus.PENDING_APPROVAL
    assert db.scalar(select_personal_workspace_count(user.id)) == 0
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
    ) == 0
    assert db.scalar(
        sa.select(sa.func.count())
        .select_from(UserAccountStateEvent)
        .where(UserAccountStateEvent.user_id == user.id)
    ) == original_event_count


def test_two_concurrent_approvals_create_exactly_one_workspace(engine) -> None:
    with Session(engine) as setup:
        admin = _admin(setup)
        user = _approvable_registration(setup)
        admin_id, user_id = admin.id, user.id
        setup.commit()

    barrier = threading.Barrier(2)

    def approve_once() -> str:
        with Session(engine) as session:
            actor = session.get(User, admin_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                approve_registration_request(session, user_id=user_id, actor=actor)
                session.commit()
                return "approved"
            except AccountStateConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(approve_once) for _ in range(2)]
        results = sorted(future.result() for future in futures)

    assert results == ["approved", "conflict"]
    with Session(engine) as verify:
        assert verify.scalar(select_personal_workspace_count(user_id)) == 1
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
        ) == 1
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(UserAccountStateEvent)
            .where(
                UserAccountStateEvent.user_id == user_id,
                UserAccountStateEvent.to_status == AccountStatus.ACTIVE,
            )
        ) == 1


def test_two_concurrent_normalized_registrations_create_one_user(engine) -> None:
    email = f"concurrent-{uuid.uuid4()}@example.com"
    barrier = threading.Barrier(2)

    def register_once(candidate: str) -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                _new_registration(session, email=candidate)
                session.commit()
                return "accepted"
            except RegistrationRequestConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(register_once, email.upper()),
            pool.submit(register_once, f" {email} "),
        ]
        results = sorted(future.result() for future in futures)

    assert results == ["accepted", "conflict"]
    with Session(engine) as verify:
        assert verify.scalar(
            sa.select(sa.func.count())
            .select_from(User)
            .where(User.email == email)
        ) == 1
