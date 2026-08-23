import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api.v2.dependencies import find_active_membership, require_global_admin
from app.api.v2.dependencies import require_usable_account
from app.api.v2.errors import V2APIError
from app.models import User, UserAccountStateEvent, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole
from app.schemas.v2_identity import RegistrationRequestCreate
from app.services.v2_identity import (
    AccountStateConflictError,
    AdminAccountNotFoundError,
    approve_registration_request,
    create_registration_request,
    get_admin_account,
    is_account_usable,
    reject_registration_request,
    transition_account_state,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _user(
    *,
    status: AccountStatus,
    global_role: GlobalRole | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="fixture-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=status,
        global_role=global_role,
        email_verified_at=(
            None
            if status is AccountStatus.PENDING_EMAIL_VERIFICATION
            else NOW
        ),
        status_changed_at=NOW,
        lock_version=1,
    )


def test_registration_is_pending_hashed_audited_and_has_no_workspace() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    registration = RegistrationRequestCreate(
        email="  New.User@Example.com ",
        password="plain password",
        first_name=" Ada ",
        last_name=" Lovelace ",
    )

    with patch("app.services.v2_identity.hash_password", return_value="safe-hash") as hasher:
        user = create_registration_request(db, registration_in=registration)

    assert user.email == "new.user@example.com"
    assert user.hashed_password == "safe-hash"
    assert user.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert user.global_role is None
    assert user.email_verified_at is None
    assert not is_account_usable(user)
    hasher.assert_called_once_with("plain password")
    added = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(added[0], User)
    assert isinstance(added[1], UserAccountStateEvent)
    assert added[1].from_status is None
    assert added[1].to_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert not any(isinstance(value, (Workspace, WorkspaceMember)) for value in added)
    assert db.flush.call_count == 2
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("global_role", "GLOBAL_ADMIN"),
        ("account_status", "ACTIVE"),
        ("owner_user_id", str(uuid.uuid4())),
        ("is_verified", True),
        ("email_verified_at", NOW.isoformat()),
        ("approved_by_user_id", str(uuid.uuid4())),
        ("actor_user_id", str(uuid.uuid4())),
        ("workspace_id", str(uuid.uuid4())),
        ("membership_role", "OWNER"),
        ("created_by_user_id", str(uuid.uuid4())),
        ("id", str(uuid.uuid4())),
        ("scope", {"global_role": "GLOBAL_ADMIN"}),
    ],
)
def test_registration_rejects_privileged_mass_assignment(field: str, value: object) -> None:
    payload = {
        "email": "person@example.com",
        "password": "plain password",
        "first_name": "Ada",
        "last_name": "Lovelace",
        field: value,
    }
    with pytest.raises(ValidationError):
        RegistrationRequestCreate.model_validate(payload)


def test_duplicate_registration_is_neutral_and_does_not_hash_or_write() -> None:
    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()
    registration = RegistrationRequestCreate(
        email="existing@example.com",
        password="plain password",
        first_name="Ada",
        last_name="Lovelace",
    )
    with patch("app.services.v2_identity.hash_password") as hasher, pytest.raises(
        ValueError,
        match="Registration request cannot be created",
    ):
        create_registration_request(db, registration_in=registration)
    hasher.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_state_machine_allows_only_explicit_transitions_and_appends_event() -> None:
    db = MagicMock()
    user = _user(status=AccountStatus.PENDING_EMAIL_VERIFICATION)
    user.email_verified_at = NOW

    event = transition_account_state(
        db,
        user=user,
        new_status=AccountStatus.PENDING_APPROVAL,
        actor_user_id=None,
    )

    assert user.account_status == AccountStatus.PENDING_APPROVAL
    assert user.lock_version == 2
    assert event.from_status == AccountStatus.PENDING_EMAIL_VERIFICATION
    assert event.to_status == AccountStatus.PENDING_APPROVAL
    db.add.assert_called_once_with(event)
    with pytest.raises(AccountStateConflictError):
        transition_account_state(
            db,
            user=user,
            new_status=AccountStatus.DISABLED,
            actor_user_id=None,
        )


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.ACTIVE,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ],
)
def test_approval_rejects_every_state_except_pending_approval(
    status: AccountStatus,
) -> None:
    db = MagicMock()
    target = _user(status=status)
    admin = _user(status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    db.scalar.return_value = target
    with pytest.raises(AccountStateConflictError):
        approve_registration_request(db, user_id=target.id, actor=admin)
    assert target.account_status == status
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_admin_detail_is_scoped_to_pending_approval() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(AdminAccountNotFoundError):
        get_admin_account(db, user_id=uuid.uuid4())
    statement = db.scalar.call_args.args[0]
    sql = str(statement)
    assert "users.id" in sql
    assert "users.account_status" in sql


def test_approval_provisions_personal_workspace_membership_and_event() -> None:
    db = MagicMock()
    target = _user(status=AccountStatus.PENDING_APPROVAL)
    admin = _user(status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    db.scalar.side_effect = [target, None]

    result = approve_registration_request(db, user_id=target.id, actor=admin)

    assert result is target
    assert target.account_status == AccountStatus.ACTIVE
    added = [call.args[0] for call in db.add.call_args_list]
    event = next(value for value in added if isinstance(value, UserAccountStateEvent))
    workspace = next(value for value in added if isinstance(value, Workspace))
    membership = next(value for value in added if isinstance(value, WorkspaceMember))
    assert event.actor_user_id == admin.id
    assert event.from_status == AccountStatus.PENDING_APPROVAL
    assert event.to_status == AccountStatus.ACTIVE
    assert workspace.owner_user_id == target.id
    assert workspace.kind == "PERSONAL"
    assert membership.workspace_id == workspace.id
    assert membership.user_id == target.id
    assert membership.status == "ACTIVE"
    assert db.flush.call_count == 2
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_rejection_has_no_workspace_and_is_audited() -> None:
    db = MagicMock()
    target = _user(status=AccountStatus.PENDING_APPROVAL)
    admin = _user(status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    db.scalar.return_value = target

    reject_registration_request(
        db,
        user_id=target.id,
        actor=admin,
        reason="Request rejected",
    )

    assert target.account_status == AccountStatus.REJECTED
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(value, UserAccountStateEvent) for value in added)
    assert not any(isinstance(value, (Workspace, WorkspaceMember)) for value in added)
    assert db.flush.call_count == 1


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.ACTIVE,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ],
)
def test_rejection_rejects_every_state_except_pending_approval(
    status: AccountStatus,
) -> None:
    db = MagicMock()
    target = _user(status=status)
    admin = _user(status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    db.scalar.return_value = target

    with pytest.raises(AccountStateConflictError):
        reject_registration_request(
            db,
            user_id=target.id,
            actor=admin,
            reason=None,
        )

    assert target.account_status == status
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_global_admin_dependency_is_persisted_role_and_no_membership_bypass() -> None:
    ordinary = _user(status=AccountStatus.ACTIVE)
    with pytest.raises(V2APIError) as denied:
        require_global_admin(ordinary)
    assert denied.value.status_code == 403

    admin = _user(status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN)
    assert require_global_admin(admin) is admin
    db = MagicMock()
    db.scalar.return_value = None
    assert (
        find_active_membership(
            db,
            user_id=admin.id,
            workspace_id=uuid.uuid4(),
        )
        is None
    )


def test_pending_or_disabled_accounts_are_not_usable() -> None:
    for account_status in (
        AccountStatus.PENDING_EMAIL_VERIFICATION,
        AccountStatus.PENDING_APPROVAL,
        AccountStatus.REJECTED,
        AccountStatus.DISABLED,
    ):
        with pytest.raises(V2APIError) as denied:
            require_usable_account(_user(status=account_status))
        assert denied.value.status_code == 401


def test_admin_role_cannot_come_from_forged_nonpersisted_object() -> None:
    forged = SimpleNamespace(
        account_status=AccountStatus.ACTIVE,
        global_role=None,
        frontend_role="GLOBAL_ADMIN",
    )
    with pytest.raises(V2APIError):
        require_global_admin(forged)  # type: ignore[arg-type]
