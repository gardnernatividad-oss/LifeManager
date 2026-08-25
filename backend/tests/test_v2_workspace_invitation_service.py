import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceInvitation, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    InvitationStatus,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace_invitation import WorkspaceInvitationCreate
from app.services.v2_workspace import WorkspaceAccess
from app.services.v2_workspace_invitation import (
    INVITATION_LIFETIME,
    WorkspaceInvitationConflictError,
    WorkspaceInvitationNotFoundError,
    accept_workspace_invitation,
    cancel_workspace_invitation,
    create_workspace_invitation,
    reject_workspace_invitation,
)


NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _user(email: str = "member@example.com") -> User:
    return User(
        id=uuid.uuid4(), email=email, hashed_password="hash", first_name="Ana",
        last_name="Pérez", account_status=AccountStatus.ACTIVE,
    )


def _access() -> WorkspaceAccess:
    owner = _user("owner@example.com")
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=owner.id,
    )
    membership = WorkspaceMember(
        workspace_id=workspace.id, user_id=owner.id,
        status=MembershipStatus.ACTIVE,
    )
    return WorkspaceAccess(workspace, membership)


def _invitation(recipient: User, workspace_id: uuid.UUID) -> WorkspaceInvitation:
    return WorkspaceInvitation(
        id=uuid.uuid4(), workspace_id=workspace_id,
        recipient_email=recipient.email, recipient_user_id=recipient.id,
        inviter_user_id=uuid.uuid4(), status=InvitationStatus.PENDING,
        token_digest=b"digest", expires_at=NOW + timedelta(days=1),
        created_at=NOW,
    )


def test_create_derives_secure_internal_state_and_never_commits() -> None:
    db = MagicMock(spec=Session)
    recipient = _user()
    access = _access()
    db.scalar.side_effect = [access.workspace, recipient, None, None]

    invitation = create_workspace_invitation(
        db, owner_access=access,
        invitation_in=WorkspaceInvitationCreate(email=" MEMBER@EXAMPLE.COM "),
        now=NOW,
    )

    assert invitation.workspace_id == access.workspace.id
    assert invitation.recipient_user_id == recipient.id
    assert invitation.inviter_user_id == access.membership.user_id
    assert invitation.recipient_email == "member@example.com"
    assert invitation.status == InvitationStatus.PENDING
    assert invitation.expires_at == NOW + INVITATION_LIFETIME
    assert len(invitation.token_digest) == 32
    db.add.assert_called_once_with(invitation)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    first_statement = db.scalar.call_args_list[0].args[0]
    assert "FROM workspaces" in str(first_statement)
    assert first_statement._for_update_arg is not None


@pytest.mark.parametrize("membership_status", [MembershipStatus.LEFT, MembershipStatus.REMOVED])
def test_accept_reactivates_same_membership_with_privacy_reset(membership_status) -> None:
    db = MagicMock(spec=Session)
    recipient = _user()
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=uuid.uuid4(),
    )
    invitation = _invitation(recipient, workspace.id)
    membership = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace.id, user_id=recipient.id,
        status=membership_status, ended_at=NOW - timedelta(days=2),
        joined_at=NOW - timedelta(days=20),
        calendar_visibility=CalendarVisibility.SHOW_DETAILS, lock_version=3,
    )
    db.scalar.side_effect = [workspace.id, workspace, invitation, membership]

    accepted = accept_workspace_invitation(
        db, invitation_id=invitation.id, recipient=recipient, now=NOW
    )

    assert accepted.status == InvitationStatus.ACCEPTED
    assert accepted.responded_at == NOW
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.joined_at == NOW
    assert membership.ended_at is None
    assert membership.calendar_visibility == CalendarVisibility.HIDE
    assert membership.lock_version == 4
    db.add.assert_not_called()
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_expired_or_foreign_invitation_is_not_actionable() -> None:
    recipient = _user()
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    with pytest.raises(WorkspaceInvitationNotFoundError):
        reject_workspace_invitation(
            db, invitation_id=uuid.uuid4(), recipient=recipient, now=NOW
        )

    expired = _invitation(recipient, uuid.uuid4())
    expired.expires_at = NOW
    workspace = Workspace(
        id=expired.workspace_id, name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=uuid.uuid4(),
    )
    db.scalar.side_effect = [expired.workspace_id, workspace, expired]
    with pytest.raises(WorkspaceInvitationConflictError):
        reject_workspace_invitation(
            db, invitation_id=expired.id, recipient=recipient, now=NOW
        )
    db.flush.assert_not_called()


def test_invitation_mutations_lock_workspace_before_invitation() -> None:
    recipient = _user()
    owner = _user("owner@example.com")
    workspace = Workspace(
        id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED,
        owner_user_id=owner.id,
    )
    invitation = _invitation(recipient, workspace.id)

    accept_db = MagicMock(spec=Session)
    accept_db.scalar.side_effect = [workspace.id, workspace, invitation, None]
    accept_workspace_invitation(
        accept_db, invitation_id=invitation.id, recipient=recipient, now=NOW
    )
    accept_statements = [call.args[0] for call in accept_db.scalar.call_args_list]
    assert accept_statements[0]._for_update_arg is None
    assert "FROM workspaces" in str(accept_statements[1])
    assert accept_statements[1]._for_update_arg is not None
    assert "FROM workspace_invitations" in str(accept_statements[2])
    assert accept_statements[2]._for_update_arg is not None

    invitation.status = InvitationStatus.PENDING
    invitation.responded_at = None
    cancel_db = MagicMock(spec=Session)
    cancel_db.scalar.side_effect = [workspace.id, workspace, invitation]
    cancel_workspace_invitation(
        cancel_db, invitation_id=invitation.id, owner=owner, now=NOW
    )
    cancel_statements = [call.args[0] for call in cancel_db.scalar.call_args_list]
    assert cancel_statements[0]._for_update_arg is None
    assert "FROM workspaces" in str(cancel_statements[1])
    assert cancel_statements[1]._for_update_arg is not None
    assert "FROM workspace_invitations" in str(cancel_statements[2])
    assert cancel_statements[2]._for_update_arg is not None


def test_disabled_recipient_cannot_accept_without_query() -> None:
    recipient = _user()
    recipient.account_status = AccountStatus.DISABLED
    db = MagicMock(spec=Session)
    with pytest.raises(WorkspaceInvitationNotFoundError):
        accept_workspace_invitation(
            db, invitation_id=uuid.uuid4(), recipient=recipient, now=NOW
        )
    db.scalar.assert_not_called()


def test_inactive_workspace_cannot_create_invitation() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    access.workspace.lifecycle = WorkspaceLifecycle.INACTIVE

    with pytest.raises(WorkspaceInvitationConflictError):
        create_workspace_invitation(
            db,
            owner_access=access,
            invitation_in=WorkspaceInvitationCreate(email="member@example.com"),
            now=NOW,
        )

    db.scalar.assert_not_called()
    db.flush.assert_not_called()


def test_creation_rechecks_workspace_under_lock_before_recipient_lookup() -> None:
    db = MagicMock(spec=Session)
    access = _access()
    db.scalar.return_value = None

    with pytest.raises(WorkspaceInvitationConflictError):
        create_workspace_invitation(
            db,
            owner_access=access,
            invitation_in=WorkspaceInvitationCreate(email="member@example.com"),
            now=NOW,
        )

    assert db.scalar.call_count == 1
    statement = db.scalar.call_args.args[0]
    assert "FROM workspaces" in str(statement)
    assert statement._for_update_arg is not None
    db.add.assert_not_called()
    db.flush.assert_not_called()
