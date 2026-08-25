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

from app.models import User, Workspace, WorkspaceInvitation, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    InvitationStatus,
    MembershipStatus,
    WorkspaceKind,
)
from app.schemas.v2_workspace_invitation import WorkspaceInvitationCreate
from app.services.v2_workspace import WorkspaceAccess
from app.services.v2_workspace_invitation import (
    WorkspaceInvitationConflictError,
    accept_workspace_invitation,
    cancel_workspace_invitation,
    create_workspace_invitation,
    reject_workspace_invitation,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Invitation tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.fail("Invitation tests require an allowlisted disposable database")
    return url


@pytest.fixture
def engine():
    value = sa.create_engine(_local_test_url())
    try:
        yield value
    finally:
        value.dispose()


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


def _user(db: Session, label: str, *, admin: bool = False) -> User:
    from app.models.enums import GlobalRole

    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(), email=f"{label}-{uuid.uuid4()}@example.com".lower(),
        hashed_password="fixture-hash", first_name=label, last_name="Invitation",
        timezone="America/Lima", account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if admin else None,
        email_verified_at=now, status_changed_at=now,
    )
    db.add(user)
    db.flush()
    return user


def _shared(db: Session, owner: User) -> WorkspaceAccess:
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=owner.id,
    )
    db.add(workspace)
    db.flush()
    member = WorkspaceMember(
        workspace_id=workspace.id, user_id=owner.id,
        status=MembershipStatus.ACTIVE,
    )
    db.add(member)
    db.flush()
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    return WorkspaceAccess(workspace, member)


def _invite(db: Session, access: WorkspaceAccess, recipient: User) -> WorkspaceInvitation:
    return create_workspace_invitation(
        db, owner_access=access,
        invitation_in=WorkspaceInvitationCreate(email=recipient.email),
    )


def test_acceptance_creates_member_and_never_changes_owner(db: Session) -> None:
    owner = _user(db, "owner")
    recipient = _user(db, "recipient")
    access = _shared(db, owner)
    invitation = _invite(db, access, recipient)
    accepted = accept_workspace_invitation(
        db, invitation_id=invitation.id, recipient=recipient
    )
    member = db.scalar(sa.select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == access.workspace.id,
        WorkspaceMember.user_id == recipient.id,
    ))
    assert accepted.status == InvitationStatus.ACCEPTED
    assert member is not None and member.status == MembershipStatus.ACTIVE
    assert member.calendar_visibility == CalendarVisibility.HIDE
    assert access.workspace.owner_user_id == owner.id


@pytest.mark.parametrize("old_status", [MembershipStatus.LEFT, MembershipStatus.REMOVED])
def test_acceptance_reactivates_historical_membership(db: Session, old_status) -> None:
    owner = _user(db, "owner-rejoin")
    recipient = _user(db, f"recipient-{old_status}")
    access = _shared(db, owner)
    old_joined = datetime.now(timezone.utc) - timedelta(days=30)
    member = WorkspaceMember(
        workspace_id=access.workspace.id, user_id=recipient.id,
        status=old_status, joined_at=old_joined,
        ended_at=datetime.now(timezone.utc) - timedelta(days=1),
        calendar_visibility=CalendarVisibility.SHOW_DETAILS,
    )
    db.add(member)
    db.flush()
    original_id = member.id
    invitation = _invite(db, access, recipient)
    accept_workspace_invitation(db, invitation_id=invitation.id, recipient=recipient)
    assert member.id == original_id
    assert member.status == MembershipStatus.ACTIVE
    assert member.ended_at is None
    assert member.joined_at > old_joined
    assert member.calendar_visibility == CalendarVisibility.HIDE
    assert member.lock_version == 2


def test_personal_and_duplicate_and_active_member_protections(db: Session) -> None:
    owner = _user(db, "owner-protection")
    recipient = _user(db, "recipient-protection")
    personal = Workspace(
        id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL,
        owner_user_id=owner.id,
    )
    db.add(personal)
    db.flush()
    owner_member = WorkspaceMember(
        workspace_id=personal.id, user_id=owner.id,
        status=MembershipStatus.ACTIVE,
    )
    db.add(owner_member)
    db.flush()
    with pytest.raises(WorkspaceInvitationConflictError):
        _invite(db, WorkspaceAccess(personal, owner_member), recipient)

    shared = _shared(db, owner)
    _invite(db, shared, recipient)
    with pytest.raises(WorkspaceInvitationConflictError):
        _invite(db, shared, recipient)

    active = WorkspaceMember(
        workspace_id=shared.workspace.id, user_id=recipient.id,
        status=MembershipStatus.ACTIVE,
    )
    db.add(active)
    db.flush()
    pending = db.scalar(sa.select(WorkspaceInvitation).where(
        WorkspaceInvitation.workspace_id == shared.workspace.id,
        WorkspaceInvitation.recipient_user_id == recipient.id,
    ))
    assert pending is not None
    pending.status = InvitationStatus.CANCELLED
    pending.cancelled_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(WorkspaceInvitationConflictError):
        _invite(db, shared, recipient)

    with pytest.raises(WorkspaceInvitationConflictError):
        _invite(db, shared, owner)


def test_expired_invitation_is_non_actionable_and_can_be_replaced(db: Session) -> None:
    owner = _user(db, "expiry-owner")
    recipient = _user(db, "expiry-recipient")
    access = _shared(db, owner)
    old_time = datetime.now(timezone.utc) - timedelta(days=15)
    expired = create_workspace_invitation(
        db, owner_access=access,
        invitation_in=WorkspaceInvitationCreate(email=recipient.email),
        now=old_time,
    )
    with pytest.raises(WorkspaceInvitationConflictError):
        accept_workspace_invitation(
            db, invitation_id=expired.id, recipient=recipient,
            now=datetime.now(timezone.utc),
        )
    replacement = _invite(db, access, recipient)
    assert expired.status == InvitationStatus.EXPIRED
    assert expired.responded_at is not None
    assert replacement.status == InvitationStatus.PENDING


def test_concurrent_double_acceptance_has_one_terminal_winner(engine) -> None:
    with Session(engine) as setup:
        owner = _user(setup, "race-owner")
        recipient = _user(setup, "race-recipient")
        access = _shared(setup, owner)
        invitation = _invite(setup, access, recipient)
        invitation_id, recipient_id = invitation.id, recipient.id
        setup.commit()

    barrier = threading.Barrier(2)

    def accept_once() -> str:
        with Session(engine) as session:
            recipient = session.get(User, recipient_id)
            assert recipient is not None
            barrier.wait(timeout=10)
            try:
                accept_workspace_invitation(
                    session, invitation_id=invitation_id, recipient=recipient
                )
                session.commit()
                return "accepted"
            except WorkspaceInvitationConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (
            pool.submit(accept_once), pool.submit(accept_once)
        )]
    assert sorted(outcomes) == ["accepted", "conflict"]
    with Session(engine) as verify:
        invitation = verify.get(WorkspaceInvitation, invitation_id)
        assert invitation is not None and invitation.status == InvitationStatus.ACCEPTED
        assert verify.scalar(sa.select(sa.func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == recipient_id,
        )) == 1


def test_concurrent_duplicate_creation_has_one_pending_invitation(engine) -> None:
    with Session(engine) as setup:
        owner = _user(setup, "duplicate-owner")
        recipient = _user(setup, "duplicate-recipient")
        access = _shared(setup, owner)
        ids = owner.id, recipient.id, access.workspace.id
        setup.commit()
    owner_id, recipient_id, workspace_id = ids
    barrier = threading.Barrier(2)

    def create_once() -> str:
        with Session(engine) as session:
            owner = session.get(User, owner_id)
            recipient = session.get(User, recipient_id)
            workspace = session.get(Workspace, workspace_id)
            membership = session.scalar(sa.select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == owner_id,
            ))
            assert owner and recipient and workspace and membership
            barrier.wait(timeout=10)
            try:
                _invite(session, WorkspaceAccess(workspace, membership), recipient)
                session.commit()
                return "created"
            except WorkspaceInvitationConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (
            pool.submit(create_once), pool.submit(create_once)
        )]
    assert sorted(outcomes) == ["conflict", "created"]
    with Session(engine) as verify:
        assert verify.scalar(sa.select(sa.func.count()).select_from(
            WorkspaceInvitation
        ).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.recipient_user_id == recipient_id,
            WorkspaceInvitation.status == InvitationStatus.PENDING,
        )) == 1


def test_membership_failure_rolls_back_invitation_acceptance(engine) -> None:
    with Session(engine) as setup:
        owner = _user(setup, "rollback-owner")
        recipient = _user(setup, "rollback-recipient")
        access = _shared(setup, owner)
        invitation = _invite(setup, access, recipient)
        ids = invitation.id, recipient.id
        setup.commit()
    invitation_id, recipient_id = ids

    def fail_membership(*_args, **_kwargs):
        raise RuntimeError("forced membership failure")

    event.listen(WorkspaceMember, "before_insert", fail_membership)
    try:
        with Session(engine) as session:
            recipient = session.get(User, recipient_id)
            assert recipient is not None
            with pytest.raises(RuntimeError, match="forced membership failure"):
                accept_workspace_invitation(
                    session, invitation_id=invitation_id, recipient=recipient
                )
            session.rollback()
    finally:
        event.remove(WorkspaceMember, "before_insert", fail_membership)

    with Session(engine) as verify:
        invitation = verify.get(WorkspaceInvitation, invitation_id)
        assert invitation is not None
        assert invitation.status == InvitationStatus.PENDING
        assert invitation.responded_at is None
        assert verify.scalar(sa.select(sa.func.count()).select_from(
            WorkspaceMember
        ).where(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == recipient_id,
        )) == 0


@pytest.mark.parametrize("competing_action", ["reject", "cancel"])
def test_acceptance_race_has_single_terminal_outcome(engine, competing_action) -> None:
    with Session(engine) as setup:
        owner = _user(setup, f"race-owner-{competing_action}")
        recipient = _user(setup, f"race-recipient-{competing_action}")
        access = _shared(setup, owner)
        invitation = _invite(setup, access, recipient)
        ids = invitation.id, recipient.id, owner.id
        setup.commit()
    invitation_id, recipient_id, owner_id = ids
    barrier = threading.Barrier(2)

    def run(action: str) -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                if action == "accept":
                    accept_workspace_invitation(
                        session, invitation_id=invitation_id,
                        recipient=session.get(User, recipient_id),
                    )
                elif action == "reject":
                    reject_workspace_invitation(
                        session, invitation_id=invitation_id,
                        recipient=session.get(User, recipient_id),
                    )
                else:
                    cancel_workspace_invitation(
                        session, invitation_id=invitation_id,
                        owner=session.get(User, owner_id),
                    )
                session.commit()
                return action
            except WorkspaceInvitationConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (
            pool.submit(run, "accept"), pool.submit(run, competing_action)
        )]
    assert outcomes.count("conflict") == 1
    with Session(engine) as verify:
        invitation = verify.get(WorkspaceInvitation, invitation_id)
        assert invitation is not None
        assert invitation.status in {
            InvitationStatus.ACCEPTED,
            InvitationStatus.REJECTED,
            InvitationStatus.CANCELLED,
        }
