import os
import uuid

from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    GlobalRole,
    MembershipStatus,
    WorkspaceKind,
)
from app.services.v2_workspace import (
    WorkspaceAccessNotFoundError,
    resolve_active_workspace_access,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("V2 Workspace tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("V2 Workspace tests require an allowlisted disposable database")
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
        email=f"{label}-{uuid.uuid4()}@example.com",
        hashed_password="fixture-hash",
        first_name=label,
        last_name="Workspace",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if admin else None,
        email_verified_at=now,
        status_changed_at=now,
    )
    db.add(user)
    db.flush()
    return user


def _workspace(
    db: Session,
    owner: User,
    *,
    kind: WorkspaceKind,
) -> tuple[Workspace, WorkspaceMember]:
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Personal" if kind == WorkspaceKind.PERSONAL else "Familia",
        kind=kind,
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
    return workspace, membership


def test_personal_workspace_unique_per_owner(db: Session) -> None:
    owner = _user(db, "owner")
    _workspace(db, owner, kind=WorkspaceKind.PERSONAL)

    savepoint = db.begin_nested()
    try:
        db.add(
            Workspace(
                id=uuid.uuid4(),
                name="Otra",
                kind=WorkspaceKind.PERSONAL,
                owner_user_id=owner.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        savepoint.rollback()


def test_owner_must_keep_active_membership(db: Session) -> None:
    owner = _user(db, "owner")
    _, membership = _workspace(db, owner, kind=WorkspaceKind.SHARED)

    savepoint = db.begin_nested()
    try:
        membership.status = MembershipStatus.REMOVED
        membership.ended_at = datetime.now(timezone.utc)
        db.flush()
        with pytest.raises(IntegrityError):
            db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    finally:
        savepoint.rollback()


def test_access_is_workspace_scoped_and_global_admin_has_no_bypass(
    db: Session,
) -> None:
    owner_a = _user(db, "owner-a")
    owner_b = _user(db, "owner-b")
    admin = _user(db, "admin", admin=True)
    workspace_a, _ = _workspace(db, owner_a, kind=WorkspaceKind.PERSONAL)
    workspace_b, _ = _workspace(db, owner_b, kind=WorkspaceKind.SHARED)

    assert resolve_active_workspace_access(
        db, account=owner_a, workspace_id=workspace_a.id
    ).workspace.id == workspace_a.id
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=owner_a, workspace_id=workspace_b.id
        )
    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=admin, workspace_id=workspace_a.id
        )
