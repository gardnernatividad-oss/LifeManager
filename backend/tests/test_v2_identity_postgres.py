import os
import uuid

from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import User, UserAccountStateEvent, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, WorkspaceKind
from app.schemas.v2_identity import RegistrationRequestCreate
from app.services.v2_identity import (
    AccountStateConflictError,
    approve_registration_request,
    create_registration_request,
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
def db():
    engine = sa.create_engine(_local_test_url())
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


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


def select_personal_workspace_count(user_id: uuid.UUID):
    return (
        sa.select(sa.func.count())
        .select_from(Workspace)
        .where(
            Workspace.owner_user_id == user_id,
            Workspace.kind == WorkspaceKind.PERSONAL,
        )
    )


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
