import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

from sqlalchemy.orm import Session

from app.models import Category, MasterTask, Task, User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace_lifecycle import (
    MemberExitResolution,
    ResponsibilityDirective,
)
from app.services.v2_workspace import (
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
    resolve_active_workspace_access,
)
from app.services.v2_workspace_lifecycle import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecyclePermissionError,
    deactivate_shared_workspace,
    hard_delete_shared_workspace,
    transfer_workspace_ownership,
    workspace_can_be_hard_deleted,
)
from app.services.v2_workspace_member import remove_workspace_member


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _url() -> str:
    value = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not value:
        pytest.skip("disposable PostgreSQL URL is not configured")
    parsed = urlparse(value.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("remote PostgreSQL refused")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.fail("non-disposable PostgreSQL refused")
    return value


@pytest.fixture
def engine():
    engine = sa.create_engine(_url())
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


def _user(db: Session, label: str) -> User:
    user = User(
        id=uuid.uuid4(), email=f"{label}-{uuid.uuid4()}@example.com",
        hashed_password="hash", first_name=label, last_name="Test",
        timezone="America/Lima", account_status=AccountStatus.ACTIVE,
        email_verified_at=NOW, status_changed_at=NOW,
    )
    db.add(user)
    db.flush()
    return user


def _shared(db: Session, owner: User) -> WorkspaceAccess:
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=owner.id, lifecycle=WorkspaceLifecycle.ACTIVE,
    )
    db.add(workspace)
    db.flush()
    membership = WorkspaceMember(
        workspace_id=workspace.id, user_id=owner.id,
        status=MembershipStatus.ACTIVE, joined_at=NOW,
    )
    db.add(membership)
    db.flush()
    return WorkspaceAccess(workspace, membership)


def _join(db: Session, access: WorkspaceAccess, user: User) -> WorkspaceMember:
    member = WorkspaceMember(
        workspace_id=access.workspace.id, user_id=user.id,
        status=MembershipStatus.ACTIVE, joined_at=NOW,
    )
    db.add(member)
    db.flush()
    return member


def test_transfer_preserves_former_owner_and_inactive_denies_access(db: Session) -> None:
    owner = _user(db, "Owner")
    target = _user(db, "Target")
    access = _shared(db, owner)
    target_membership = _join(db, access, target)

    transfer_workspace_ownership(
        db, owner_access=access, target_user_id=target.id
    )
    assert access.workspace.owner_user_id == target.id
    assert access.membership.status == MembershipStatus.ACTIVE
    assert target_membership.status == MembershipStatus.ACTIVE

    target_access = WorkspaceAccess(access.workspace, target_membership)
    deactivate_shared_workspace(db, owner_access=target_access, now=NOW)
    assert access.workspace.lifecycle == WorkspaceLifecycle.INACTIVE
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=target, workspace_id=access.workspace.id
        )


def test_empty_delete_and_current_state_eligibility(db: Session) -> None:
    owner = _user(db, "Empty")
    access = _shared(db, owner)
    workspace_id = access.workspace.id
    assert workspace_can_be_hard_deleted(db, workspace=access.workspace)
    hard_delete_shared_workspace(db, owner_access=access)
    assert db.get(Workspace, workspace_id) is None

    owner = _user(db, "Used")
    access = _shared(db, owner)
    category = Category(
        workspace_id=access.workspace.id, name="Casa",
        normalized_name="casa", is_active=True,
    )
    db.add(category)
    db.flush()
    assert not workspace_can_be_hard_deleted(db, workspace=access.workspace)
    with pytest.raises(WorkspaceLifecycleConflictError):
        hard_delete_shared_workspace(db, owner_access=access)
    db.delete(category)
    db.flush()
    assert workspace_can_be_hard_deleted(db, workspace=access.workspace)


def test_member_future_task_reassign_and_delete_all_preserve_past(db: Session) -> None:
    owner = _user(db, "OwnerTasks")
    departing = _user(db, "Departing")
    target = _user(db, "TargetTasks")
    access = _shared(db, owner)
    departing_membership = _join(db, access, departing)
    _join(db, access, target)
    category = Category(
        workspace_id=access.workspace.id, name="Casa",
        normalized_name="casa", is_active=True,
    )
    db.add(category)
    db.flush()
    master = MasterTask(
        workspace_id=access.workspace.id, category_id=category.id,
        name="Ordenar", normalized_name="ordenar", is_active=True,
    )
    db.add(master)
    db.flush()
    future = Task(
        workspace_id=access.workspace.id, master_task_id=master.id,
        responsible_user_id=departing.id, planned_date=date(2026, 8, 30),
        created_by_user_id=owner.id,
    )
    past = Task(
        workspace_id=access.workspace.id, master_task_id=master.id,
        responsible_user_id=departing.id, planned_date=date(2026, 8, 20),
        created_by_user_id=owner.id,
    )
    db.add_all([future, past])
    db.flush()

    remove_workspace_member(
        db,
        owner_access=access,
        target_user_id=departing.id,
        resolution=MemberExitResolution(
            tasks=ResponsibilityDirective(
                action="REASSIGN", target_user_id=target.id
            )
        ),
        now=NOW,
    )
    assert future.responsible_user_id == target.id
    assert past.responsible_user_id == departing.id
    assert departing_membership.status == MembershipStatus.REMOVED

    departing_two = _user(db, "DeleteAll")
    member_two = _join(db, access, departing_two)
    future_two = Task(
        workspace_id=access.workspace.id, master_task_id=master.id,
        responsible_user_id=departing_two.id,
        planned_date=date(2026, 9, 1), created_by_user_id=owner.id,
    )
    db.add(future_two)
    db.flush()
    remove_workspace_member(
        db, owner_access=access, target_user_id=departing_two.id,
        resolution=MemberExitResolution(delete_all=True), now=NOW,
    )
    assert db.get(Task, future_two.id) is None
    assert member_two.status == MembershipStatus.REMOVED


def test_concurrent_transfers_leave_one_consistent_owner(engine) -> None:
    with Session(engine) as setup:
        owner = _user(setup, "RaceOwner")
        first = _user(setup, "RaceFirst")
        second = _user(setup, "RaceSecond")
        access = _shared(setup, owner)
        _join(setup, access, first)
        _join(setup, access, second)
        workspace_id = access.workspace.id
        owner_id = owner.id
        target_ids = (first.id, second.id)
        setup.commit()

    barrier = threading.Barrier(2)

    def transfer(target_id: uuid.UUID) -> str:
        with Session(engine) as session:
            workspace = session.get(Workspace, workspace_id)
            membership = session.scalar(sa.select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == owner_id,
            ))
            barrier.wait()
            try:
                transfer_workspace_ownership(
                    session,
                    owner_access=WorkspaceAccess(workspace, membership),
                    target_user_id=target_id,
                )
                session.commit()
                return "success"
            except WorkspaceLifecyclePermissionError:
                session.rollback()
                return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(transfer, target_ids))

    assert sorted(outcomes) == ["denied", "success"]
    with Session(engine) as verify:
        persisted = verify.get(Workspace, workspace_id)
        assert persisted.owner_user_id in set(target_ids)
        assert verify.scalar(sa.select(sa.func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )) == 3
