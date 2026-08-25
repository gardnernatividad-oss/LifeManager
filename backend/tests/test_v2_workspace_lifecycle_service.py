import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceInvitation, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    InvitationStatus,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace_lifecycle import MemberExitResolution
from app.services.v2_workspace import WorkspaceAccess
from app.services.v2_workspace_lifecycle import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleNotFoundError,
    deactivate_shared_workspace,
    reactivate_shared_workspace,
    hard_delete_shared_workspace,
    resolve_member_future_responsibilities,
    transfer_workspace_ownership,
    workspace_can_be_hard_deleted,
)


def test_reactivate_requires_inactive_shared_owner_and_active_owner_membership() -> None:
    db = MagicMock()
    account, access = _access(lifecycle=WorkspaceLifecycle.INACTIVE)
    access.workspace.lifecycle = WorkspaceLifecycle.INACTIVE
    access.workspace.deactivated_at = NOW
    owner_membership = access.membership
    db.scalar.side_effect = [access.workspace, owner_membership]

    result = reactivate_shared_workspace(db, owner_access=access)

    assert result is access.workspace
    assert result.lifecycle == WorkspaceLifecycle.ACTIVE
    assert result.deactivated_at is None
    assert result.lock_version == 3
    assert db.scalar.call_count == 2
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_reactivate_does_not_restore_members_or_invitations() -> None:
    db = MagicMock()
    _, access = _access(lifecycle=WorkspaceLifecycle.INACTIVE)
    access.workspace.lifecycle = WorkspaceLifecycle.INACTIVE
    access.workspace.deactivated_at = NOW
    db.scalar.side_effect = [access.workspace, access.membership]

    reactivate_shared_workspace(db, owner_access=access)

    statements = [str(call.args[0]) for call in db.scalar.call_args_list]
    assert all("workspace_invitations" not in sql for sql in statements)
    assert all("LEFT" not in sql and "REMOVED" not in sql for sql in statements)


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _user() -> User:
    return User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.com",
        hashed_password="hash", first_name="Ana", last_name="Pérez",
        timezone="America/Lima", account_status=AccountStatus.ACTIVE,
    )


def _access(*, kind=WorkspaceKind.SHARED, lifecycle=WorkspaceLifecycle.ACTIVE):
    owner = _user()
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=kind,
        owner_user_id=owner.id, lifecycle=lifecycle,
        deactivated_at=None if lifecycle == WorkspaceLifecycle.ACTIVE else NOW,
        lock_version=2,
    )
    member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace.id, user_id=owner.id,
        status=MembershipStatus.ACTIVE, joined_at=NOW, lock_version=1,
    )
    return owner, WorkspaceAccess(workspace, member)


def test_owner_structural_membership_does_not_block_hard_delete() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.side_effect = [False] * 16 + [False]
    assert workspace_can_be_hard_deleted(db, workspace=access.workspace) is True


def test_any_domain_or_historical_row_blocks_hard_delete() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.side_effect = [False, False, True]
    assert workspace_can_be_hard_deleted(db, workspace=access.workspace) is False


def test_meaningful_membership_blocks_hard_delete() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.side_effect = [False] * 16 + [True]
    assert workspace_can_be_hard_deleted(db, workspace=access.workspace) is False


def test_deactivation_preserves_memberships_and_cancels_pending_invitations() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(), workspace_id=access.workspace.id,
        recipient_email="member@example.com", inviter_user_id=access.membership.user_id,
        status=InvitationStatus.PENDING, token_digest=b"x" * 32,
        expires_at=NOW, created_at=NOW,
    )
    db.scalar.return_value = access.workspace
    db.scalars.return_value.all.return_value = [invitation]

    result = deactivate_shared_workspace(db, owner_access=access, now=NOW)

    assert result.lifecycle == WorkspaceLifecycle.INACTIVE
    assert result.deactivated_at == NOW and result.lock_version == 3
    assert invitation.status == InvitationStatus.CANCELLED
    assert invitation.cancelled_at == NOW
    db.delete.assert_not_called()
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_hard_delete_rechecks_eligibility_under_workspace_lock() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.return_value = access.workspace
    with patch(
        "app.services.v2_workspace_lifecycle.workspace_can_be_hard_deleted",
        return_value=True,
    ) as eligible:
        hard_delete_shared_workspace(db, owner_access=access)
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    eligible.assert_called_once_with(db, workspace=access.workspace)
    db.delete.assert_called_once_with(access.workspace)
    db.flush.assert_called_once_with()


def test_hard_delete_with_retained_data_is_rejected_without_delete() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.return_value = access.workspace
    with patch(
        "app.services.v2_workspace_lifecycle.workspace_can_be_hard_deleted",
        return_value=False,
    ), pytest.raises(WorkspaceLifecycleConflictError):
        hard_delete_shared_workspace(db, owner_access=access)
    db.delete.assert_not_called()
    db.flush.assert_not_called()


def test_transfer_changes_only_owner_and_keeps_former_owner_membership() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    target = _user()
    target_membership = WorkspaceMember(
        workspace_id=access.workspace.id, user_id=target.id,
        status=MembershipStatus.ACTIVE,
    )
    db.scalar.return_value = access.workspace
    db.execute.return_value.one_or_none.return_value = (target_membership, target)

    result = transfer_workspace_ownership(
        db, owner_access=access, target_user_id=target.id
    )

    assert result.owner_user_id == target.id and result.lock_version == 3
    assert access.membership.status == MembershipStatus.ACTIVE
    assert target_membership.status == MembershipStatus.ACTIVE
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    assert db.execute.call_args.args[0]._for_update_arg is not None
    db.flush.assert_called_once_with()


def test_transfer_rejects_foreign_or_inactive_target() -> None:
    db = MagicMock(spec=Session)
    _, access = _access()
    db.scalar.return_value = access.workspace
    db.execute.return_value.one_or_none.return_value = None
    with pytest.raises(WorkspaceLifecycleNotFoundError):
        transfer_workspace_ownership(
            db, owner_access=access, target_user_id=uuid.uuid4()
        )
    db.flush.assert_not_called()


def test_future_responsibilities_require_resolution_and_delete_all_is_atomic() -> None:
    db = MagicMock(spec=Session)
    user, access = _access()
    task = MagicMock(id=uuid.uuid4())
    with patch(
        "app.services.v2_workspace_lifecycle._locked_rows",
        side_effect=[[task], [], [], [], [], []],
    ), pytest.raises(WorkspaceLifecycleConflictError):
        resolve_member_future_responsibilities(
            db, workspace=access.workspace, departing_user=user,
            actor_user_id=user.id,
            resolution=None, now=NOW,
        )
    db.delete.assert_not_called()

    db.reset_mock()
    with patch(
        "app.services.v2_workspace_lifecycle._locked_rows",
        side_effect=[[task], [], [], [], [], []],
    ):
        resolve_member_future_responsibilities(
            db, workspace=access.workspace, departing_user=user,
            actor_user_id=user.id,
            resolution=MemberExitResolution(delete_all=True), now=NOW,
        )
    db.delete.assert_called_once_with(task)
    db.commit.assert_not_called()


def test_project_reassignment_records_leader_history() -> None:
    db = MagicMock(spec=Session)
    actor, access = _access()
    target = _user()
    project = MagicMock(id=uuid.uuid4(), leader_user_id=actor.id, lock_version=1)
    resolution = MemberExitResolution(
        projects={"action": "REASSIGN", "target_user_id": target.id}
    )
    with patch(
        "app.services.v2_workspace_lifecycle._locked_rows",
        side_effect=[[], [], [project], [], [], []],
    ), patch(
        "app.services.v2_workspace_lifecycle._lock_reassignment_targets"
    ):
        resolve_member_future_responsibilities(
            db,
            workspace=access.workspace,
            departing_user=actor,
            actor_user_id=access.membership.user_id,
            resolution=resolution,
            now=NOW,
        )

    assert project.leader_user_id == target.id and project.lock_version == 2
    history = db.add.call_args.args[0]
    assert history.project_id == project.id
    assert history.leader_user_id == target.id
    assert history.actor_user_id == access.membership.user_id
