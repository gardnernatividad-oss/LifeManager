import uuid

from unittest.mock import MagicMock

import pytest

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    GlobalRole,
    MembershipStatus,
    WorkspaceKind,
)
from app.services.v2_workspace import (
    PersonalWorkspaceInvariantError,
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
    WorkspaceInvariantError,
    WorkspaceOwnerRequiredError,
    create_shared_workspace,
    ensure_member_addition_allowed,
    ensure_membership_can_end,
    ensure_ownership_transfer_allowed,
    ensure_workspace_can_be_deleted,
    ensure_workspace_kind_unchanged,
    require_workspace_owner,
    resolve_active_workspace_access,
)
from app.schemas.v2_workspace import SharedWorkspaceCreate


def _account(*, global_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="hash",
        first_name="Ana",
        last_name="Pérez",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if global_admin else None,
    )


def _workspace(owner: User, *, kind: WorkspaceKind) -> Workspace:
    return Workspace(
        id=uuid.uuid4(),
        name="Personal" if kind == WorkspaceKind.PERSONAL else "Familia",
        kind=kind,
        owner_user_id=owner.id,
    )


def _membership(workspace: Workspace, user: User) -> WorkspaceMember:
    return WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        status=MembershipStatus.ACTIVE,
    )


def test_active_access_uses_persisted_account_and_membership() -> None:
    db = MagicMock(spec=Session)
    account = _account()
    workspace = _workspace(account, kind=WorkspaceKind.PERSONAL)
    membership = _membership(workspace, account)
    db.execute.return_value.one_or_none.return_value = (workspace, membership)

    access = resolve_active_workspace_access(
        db, account=account, workspace_id=workspace.id
    )

    assert access == WorkspaceAccess(workspace, membership)
    statement = db.execute.call_args.args[0]
    parameters = set(statement.compile().params.values())
    assert {account.id, workspace.id, MembershipStatus.ACTIVE} <= parameters
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("global_admin", [False, True])
def test_missing_or_foreign_membership_is_safely_hidden(global_admin: bool) -> None:
    db = MagicMock(spec=Session)
    account = _account(global_admin=global_admin)
    db.execute.return_value.one_or_none.return_value = None

    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=account, workspace_id=uuid.uuid4()
        )


def test_inactive_account_is_rejected_without_query() -> None:
    db = MagicMock(spec=Session)
    account = _account()
    account.account_status = AccountStatus.DISABLED

    with pytest.raises(WorkspaceAccessNotFoundError):
        resolve_active_workspace_access(
            db, account=account, workspace_id=uuid.uuid4()
        )
    db.execute.assert_not_called()


def test_owner_authority_is_derived_from_workspace_owner() -> None:
    owner = _account()
    member = _account()
    workspace = _workspace(owner, kind=WorkspaceKind.SHARED)

    owner_access = WorkspaceAccess(workspace, _membership(workspace, owner))
    assert require_workspace_owner(owner_access) is owner_access

    with pytest.raises(WorkspaceOwnerRequiredError):
        require_workspace_owner(
            WorkspaceAccess(workspace, _membership(workspace, member))
        )


def test_personal_workspace_rejects_foreign_member_and_owner_mutations() -> None:
    owner = _account()
    workspace = _workspace(owner, kind=WorkspaceKind.PERSONAL)

    ensure_member_addition_allowed(workspace, user_id=owner.id)
    with pytest.raises(PersonalWorkspaceInvariantError):
        ensure_member_addition_allowed(workspace, user_id=uuid.uuid4())
    with pytest.raises(WorkspaceInvariantError):
        ensure_membership_can_end(workspace, user_id=owner.id)
    with pytest.raises(PersonalWorkspaceInvariantError):
        ensure_workspace_can_be_deleted(workspace)
    with pytest.raises(PersonalWorkspaceInvariantError):
        ensure_ownership_transfer_allowed(workspace)
    with pytest.raises(PersonalWorkspaceInvariantError):
        ensure_workspace_kind_unchanged(
            workspace, kind=WorkspaceKind.SHARED
        )


def test_shared_workspace_allows_future_collaboration_operations() -> None:
    owner = _account()
    member = _account()
    workspace = _workspace(owner, kind=WorkspaceKind.SHARED)

    ensure_member_addition_allowed(workspace, user_id=member.id)
    ensure_membership_can_end(workspace, user_id=member.id)
    ensure_workspace_can_be_deleted(workspace)
    ensure_ownership_transfer_allowed(workspace)
    ensure_workspace_kind_unchanged(workspace, kind=WorkspaceKind.SHARED)


def test_create_shared_workspace_derives_owner_and_active_membership() -> None:
    db = MagicMock(spec=Session)
    creator = _account()

    workspace = create_shared_workspace(
        db,
        creator=creator,
        workspace_in=SharedWorkspaceCreate(name="  Familia   Pérez  "),
    )

    assert workspace.name == "Familia Pérez"
    assert workspace.kind == WorkspaceKind.SHARED
    assert workspace.owner_user_id == creator.id
    assert db.add.call_args_list[0].args == (workspace,)
    membership = db.add.call_args_list[1].args[0]
    assert membership.workspace_id == workspace.id
    assert membership.user_id == creator.id
    assert membership.status == MembershipStatus.ACTIVE
    assert db.flush.call_count == 2
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_shared_workspace_flushes_workspace_before_membership() -> None:
    db = MagicMock(spec=Session)
    creator = _account()
    events: list[str] = []
    db.add.side_effect = lambda _value: events.append("add")
    db.flush.side_effect = lambda: events.append("flush")

    create_shared_workspace(
        db,
        creator=creator,
        workspace_in=SharedWorkspaceCreate(name="Familia"),
    )

    assert events == ["add", "flush", "add", "flush"]


def test_create_shared_workspace_rejects_non_active_creator() -> None:
    db = MagicMock(spec=Session)
    creator = _account()
    creator.account_status = AccountStatus.DISABLED

    with pytest.raises(WorkspaceAccessNotFoundError):
        create_shared_workspace(
            db,
            creator=creator,
            workspace_in=SharedWorkspaceCreate(name="Familia"),
        )
    db.add.assert_not_called()
    db.flush.assert_not_called()
    create_shared_workspace,
