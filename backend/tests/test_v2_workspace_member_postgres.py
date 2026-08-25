import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    GlobalRole,
    MembershipStatus,
    WorkspaceKind,
)
from app.schemas.v2_workspace_invitation import WorkspaceInvitationCreate
from app.services.v2_workspace import (
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
    resolve_active_workspace_access,
)
from app.services.v2_workspace_invitation import (
    accept_workspace_invitation,
    create_workspace_invitation,
)
from app.services.v2_workspace_member import (
    WorkspaceMemberConflictError,
    leave_shared_workspace,
    list_workspace_members,
    remove_workspace_member,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Membership tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("Membership tests require an allowlisted disposable database")
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
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email=f"{label}-{uuid.uuid4()}@example.com".lower(),
        hashed_password="fixture-hash",
        first_name=label,
        last_name="Membership",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if admin else None,
        email_verified_at=now,
        status_changed_at=now,
    )
    db.add(user)
    db.flush()
    return user


def _shared(db: Session, owner: User) -> WorkspaceAccess:
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Familia",
        kind=WorkspaceKind.SHARED,
        owner_user_id=owner.id,
    )
    db.add(workspace)
    db.flush()
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=owner.id,
        status=MembershipStatus.ACTIVE,
    )
    db.add(membership)
    db.flush()
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    return WorkspaceAccess(workspace, membership)


def _add_member(
    db: Session,
    access: WorkspaceAccess,
    user: User,
) -> WorkspaceMember:
    membership = WorkspaceMember(
        workspace_id=access.workspace.id,
        user_id=user.id,
        status=MembershipStatus.ACTIVE,
        calendar_visibility=CalendarVisibility.SHOW_DETAILS,
    )
    db.add(membership)
    db.flush()
    return membership


def test_listing_exit_removal_and_access_revocation(db: Session) -> None:
    owner = _user(db, "owner")
    leaving = _user(db, "leaving")
    removed = _user(db, "removed")
    access = _shared(db, owner)
    leaving_member = _add_member(db, access, leaving)
    removed_member = _add_member(db, access, removed)

    rows = list_workspace_members(
        db,
        access=WorkspaceAccess(access.workspace, leaving_member),
    )
    assert {user.id for _, user in rows} == {owner.id, leaving.id, removed.id}
    assert rows[0][1].id == owner.id

    leave_shared_workspace(
        db,
        access=WorkspaceAccess(access.workspace, leaving_member),
        account=leaving,
    )
    remove_workspace_member(
        db,
        owner_access=access,
        target_user_id=removed.id,
    )
    assert leaving_member.status == MembershipStatus.LEFT
    assert removed_member.status == MembershipStatus.REMOVED
    assert leaving_member.ended_at is not None
    assert removed_member.ended_at is not None
    assert leaving_member.calendar_visibility == CalendarVisibility.SHOW_DETAILS
    assert removed_member.calendar_visibility == CalendarVisibility.SHOW_DETAILS
    for account in (leaving, removed):
        with pytest.raises(WorkspaceAccessNotFoundError):
            resolve_active_workspace_access(
                db, account=account, workspace_id=access.workspace.id
            )


@pytest.mark.parametrize(
    "exit_status",
    [MembershipStatus.LEFT, MembershipStatus.REMOVED],
)
def test_fresh_invitation_reactivates_same_row_with_private_default(
    db: Session,
    exit_status: MembershipStatus,
) -> None:
    owner = _user(db, f"owner-{exit_status}")
    member = _user(db, f"member-{exit_status}")
    access = _shared(db, owner)
    membership = _add_member(db, access, member)
    original_id = membership.id

    if exit_status == MembershipStatus.LEFT:
        leave_shared_workspace(
            db,
            access=WorkspaceAccess(access.workspace, membership),
            account=member,
        )
    else:
        remove_workspace_member(
            db, owner_access=access, target_user_id=member.id
        )
    exit_version = membership.lock_version

    invitation = create_workspace_invitation(
        db,
        owner_access=access,
        invitation_in=WorkspaceInvitationCreate(email=member.email),
    )
    accept_workspace_invitation(
        db,
        invitation_id=invitation.id,
        recipient=member,
    )
    assert membership.id == original_id
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.ended_at is None
    assert membership.calendar_visibility == CalendarVisibility.HIDE
    assert membership.lock_version == exit_version + 1


def test_account_state_and_global_admin_never_bypass_membership(db: Session) -> None:
    owner = _user(db, "owner-account")
    member = _user(db, "member-account")
    admin = _user(db, "admin", admin=True)
    access = _shared(db, owner)
    membership = _add_member(db, access, member)

    member.account_status = AccountStatus.DISABLED
    db.flush()
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=member, workspace_id=access.workspace.id
        )
    member.account_status = AccountStatus.ACTIVE
    db.flush()
    assert resolve_active_workspace_access(
        db, account=member, workspace_id=access.workspace.id
    ).membership.id == membership.id

    leave_shared_workspace(
        db,
        access=WorkspaceAccess(access.workspace, membership),
        account=member,
    )
    member.account_status = AccountStatus.DISABLED
    db.flush()
    member.account_status = AccountStatus.ACTIVE
    db.flush()
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=member, workspace_id=access.workspace.id
        )
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=admin, workspace_id=access.workspace.id
        )


def test_personal_owner_cannot_leave(db: Session) -> None:
    owner = _user(db, "personal-owner")
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Personal",
        kind=WorkspaceKind.PERSONAL,
        owner_user_id=owner.id,
    )
    db.add(workspace)
    db.flush()
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=owner.id,
        status=MembershipStatus.ACTIVE,
    )
    db.add(membership)
    db.flush()
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    db.connection().exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    with pytest.raises(WorkspaceMemberConflictError):
        leave_shared_workspace(
            db,
            access=WorkspaceAccess(workspace, membership),
            account=owner,
        )


def test_removal_and_leave_race_has_one_terminal_winner(engine) -> None:
    with Session(engine) as setup:
        owner = _user(setup, "race-owner")
        member = _user(setup, "race-member")
        access = _shared(setup, owner)
        _add_member(setup, access, member)
        owner_id, member_id, workspace_id = owner.id, member.id, access.workspace.id
        setup.commit()

    barrier = threading.Barrier(2)

    def mutate(action: str) -> str:
        with Session(engine) as session:
            owner = session.get(User, owner_id)
            member = session.get(User, member_id)
            workspace = session.get(Workspace, workspace_id)
            owner_membership = session.scalar(sa.select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == owner_id,
            ))
            target_membership = session.scalar(sa.select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == member_id,
            ))
            assert owner and member and workspace and owner_membership and target_membership
            barrier.wait(timeout=10)
            try:
                if action == "remove":
                    remove_workspace_member(
                        session,
                        owner_access=WorkspaceAccess(workspace, owner_membership),
                        target_user_id=member_id,
                    )
                else:
                    leave_shared_workspace(
                        session,
                        access=WorkspaceAccess(workspace, target_membership),
                        account=member,
                    )
                session.commit()
                return action
            except WorkspaceMemberConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (
            pool.submit(mutate, "remove"),
            pool.submit(mutate, "leave"),
        )]
    assert outcomes.count("conflict") == 1
    with Session(engine) as verify:
        membership = verify.scalar(sa.select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_id,
        ))
        assert membership is not None
        assert membership.status in {MembershipStatus.LEFT, MembershipStatus.REMOVED}
        assert membership.ended_at is not None
        assert verify.scalar(sa.select(sa.func.count()).select_from(
            WorkspaceMember
        ).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_id,
        )) == 1


@pytest.mark.parametrize("action", ["remove", "leave"])
def test_duplicate_exit_requests_have_one_winner(engine, action: str) -> None:
    with Session(engine) as setup:
        owner = _user(setup, f"duplicate-owner-{action}")
        member = _user(setup, f"duplicate-member-{action}")
        access = _shared(setup, owner)
        _add_member(setup, access, member)
        owner_id, member_id, workspace_id = owner.id, member.id, access.workspace.id
        setup.commit()
    barrier = threading.Barrier(2)

    def mutate() -> str:
        with Session(engine) as session:
            owner = session.get(User, owner_id)
            member = session.get(User, member_id)
            workspace = session.get(Workspace, workspace_id)
            actor_id = owner_id if action == "remove" else member_id
            actor_membership = session.scalar(sa.select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == actor_id,
            ))
            assert owner and member and workspace and actor_membership
            barrier.wait(timeout=10)
            try:
                if action == "remove":
                    remove_workspace_member(
                        session,
                        owner_access=WorkspaceAccess(workspace, actor_membership),
                        target_user_id=member_id,
                    )
                else:
                    leave_shared_workspace(
                        session,
                        access=WorkspaceAccess(workspace, actor_membership),
                        account=member,
                    )
                session.commit()
                return "changed"
            except WorkspaceMemberConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (
            pool.submit(mutate), pool.submit(mutate)
        )]
    assert sorted(outcomes) == ["changed", "conflict"]
