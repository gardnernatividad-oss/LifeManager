import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    GlobalRole,
    MembershipStatus,
    WorkspaceKind,
)
from app.services.v2_workspace import WorkspaceAccess
from app.services.v2_workspace_member import (
    WorkspaceMemberConflictError,
    WorkspaceMemberNotFoundError,
    leave_shared_workspace,
    list_workspace_members,
    remove_workspace_member,
)


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _user(*, admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="hash",
        first_name="Ana",
        last_name="Pérez",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if admin else None,
    )


def _access(*, kind: WorkspaceKind = WorkspaceKind.SHARED) -> WorkspaceAccess:
    owner = _user()
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Familia",
        kind=kind,
        owner_user_id=owner.id,
    )
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=owner.id,
        status=MembershipStatus.ACTIVE,
        joined_at=NOW - timedelta(days=10),
    )
    return WorkspaceAccess(workspace, membership)


def _member(access: WorkspaceAccess, user: User) -> WorkspaceMember:
    return WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=access.workspace.id,
        user_id=user.id,
        status=MembershipStatus.ACTIVE,
        calendar_visibility=CalendarVisibility.SHOW_DETAILS,
        joined_at=NOW - timedelta(days=5),
        lock_version=2,
    )


def test_list_members_is_read_only_and_deterministic() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    user = _user()
    membership = _member(access, user)
    db.execute.return_value.all.return_value = [(membership, user)]

    assert list_workspace_members(db, access=access) == [(membership, user)]

    statement = db.execute.call_args.args[0]
    assert str(access.workspace.id) in str(statement.compile().params.values())
    assert len(statement._order_by_clauses) == 5
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_personal_workspace_has_no_collaborative_member_list() -> None:
    db = MagicMock(spec=Session)
    with pytest.raises(WorkspaceMemberConflictError):
        list_workspace_members(db, access=_access(kind=WorkspaceKind.PERSONAL))
    db.execute.assert_not_called()


def test_owner_removes_active_ordinary_member_without_commit() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    user = _user()
    membership = _member(access, user)
    db.scalar.return_value = access.workspace
    db.execute.return_value.one_or_none.return_value = (membership, user)

    result = remove_workspace_member(
        db,
        owner_access=access,
        target_user_id=user.id,
        now=NOW,
    )

    assert result == (membership, user)
    assert membership.status == MembershipStatus.REMOVED
    assert membership.ended_at == NOW
    assert membership.joined_at == NOW - timedelta(days=5)
    assert membership.calendar_visibility == CalendarVisibility.SHOW_DETAILS
    assert membership.lock_version == 3
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    assert db.execute.call_args.args[0]._for_update_arg is not None
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_owner_and_inactive_targets_cannot_be_removed() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    db.scalar.return_value = access.workspace
    with pytest.raises(WorkspaceMemberConflictError):
        remove_workspace_member(
            db,
            owner_access=access,
            target_user_id=access.workspace.owner_user_id,
            now=NOW,
        )
    db.execute.assert_not_called()

    user = _user()
    membership = _member(access, user)
    membership.status = MembershipStatus.LEFT
    membership.ended_at = NOW - timedelta(days=1)
    db.execute.return_value.one_or_none.return_value = (membership, user)
    with pytest.raises(WorkspaceMemberConflictError):
        remove_workspace_member(
            db, owner_access=access, target_user_id=user.id, now=NOW
        )
    db.flush.assert_not_called()


def test_missing_or_foreign_target_is_hidden() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    db.scalar.return_value = access.workspace
    db.execute.return_value.one_or_none.return_value = None
    with pytest.raises(WorkspaceMemberNotFoundError):
        remove_workspace_member(
            db, owner_access=access, target_user_id=uuid.uuid4(), now=NOW
        )


def test_ordinary_member_leaves_without_commit_or_privacy_reset() -> None:
    db = MagicMock(spec=Session)
    owner_access = _access()
    account = _user()
    membership = _member(owner_access, account)
    member_access = WorkspaceAccess(owner_access.workspace, membership)
    db.scalar.side_effect = [owner_access.workspace, membership]

    result = leave_shared_workspace(
        db, access=member_access, account=account, now=NOW
    )

    assert result is membership
    assert membership.status == MembershipStatus.LEFT
    assert membership.ended_at == NOW
    assert membership.calendar_visibility == CalendarVisibility.SHOW_DETAILS
    assert membership.lock_version == 3
    assert all(
        call.args[0]._for_update_arg is not None
        for call in db.scalar.call_args_list
    )
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("admin", [False, True])
def test_owner_cannot_leave_even_when_global_admin(admin: bool) -> None:
    db = MagicMock(spec=Session)
    access = _access()
    owner = _user(admin=admin)
    owner.id = access.workspace.owner_user_id
    db.scalar.return_value = access.workspace
    with pytest.raises(WorkspaceMemberConflictError):
        leave_shared_workspace(db, access=access, account=owner, now=NOW)
    assert db.scalar.call_count == 1
    db.flush.assert_not_called()
