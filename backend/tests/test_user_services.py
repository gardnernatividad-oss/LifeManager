import uuid

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    User,
    Workspace,
    WorkspaceKind,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceTrackingMetadata,
)
from app.schemas.user import UserCreate, UserUpdate
from app.services.user import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
    update_user_profile,
)


def _registration_input(email: str = "Ada@Example.com") -> UserCreate:
    return UserCreate(
        email=email,
        password="plain-secret",
        first_name=" Ada ",
        last_name=" Lovelace ",
    )


def _provisioning_session() -> MagicMock:
    db = MagicMock(spec=Session)
    db.scalar.return_value = None

    def assign_ids() -> None:
        for call in db.add.call_args_list:
            entity = call.args[0]
            if hasattr(entity, "id") and entity.id is None:
                entity.id = uuid.uuid4()

    db.flush.side_effect = assign_ids
    return db


def test_registration_provisions_exact_target_aggregate() -> None:
    db = _provisioning_session()

    with patch("app.services.user.hash_password", return_value="secure-hash"):
        user = register_user(db, user_in=_registration_input())

    added = [call.args[0] for call in db.add.call_args_list]
    assert len(added) == 2
    assert added[0] is user
    workspace = added[1]
    assert isinstance(workspace, Workspace)
    assert workspace.name == "Personal"
    assert workspace.kind is WorkspaceKind.PERSONAL

    membership, metadata = db.add_all.call_args.args[0]
    assert isinstance(membership, WorkspaceMember)
    assert membership.user_id == user.id
    assert membership.workspace_id == workspace.id
    assert membership.role is WorkspaceRole.OWNER
    assert isinstance(metadata, WorkspaceTrackingMetadata)
    assert metadata.workspace_id == workspace.id
    assert user.email == "ada@example.com"
    assert user.hashed_password == "secure-hash"
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.is_active is True
    assert user.is_verified is False
    assert not hasattr(user, "username")
    assert not hasattr(user, "full_name")
    assert db.flush.call_count == 3
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_two_registrations_create_independent_personal_workspaces() -> None:
    first_db = _provisioning_session()
    second_db = _provisioning_session()

    register_user(first_db, user_in=_registration_input("one@example.com"))
    register_user(second_db, user_in=_registration_input("two@example.com"))

    first_workspace = first_db.add.call_args_list[1].args[0]
    second_workspace = second_db.add.call_args_list[1].args[0]
    assert first_workspace.name == second_workspace.name == "Personal"
    assert first_workspace.id != second_workspace.id


def test_duplicate_email_is_rejected_before_writes() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = User(id=uuid.uuid4(), email="ada@example.com")

    with pytest.raises(EmailAlreadyRegisteredError, match="Email already registered"):
        register_user(db, user_in=_registration_input())

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_duplicate_email_race_is_translated() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    original = MagicMock()
    original.diag.constraint_name = "uq_users_email"
    db.flush.side_effect = IntegrityError("insert", {}, original)

    with pytest.raises(EmailAlreadyRegisteredError, match="Email already registered"):
        register_user(db, user_in=_registration_input())

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_newly_registered_user_can_authenticate() -> None:
    registration_db = _provisioning_session()
    user = register_user(registration_db, user_in=_registration_input())
    authentication_db = MagicMock(spec=Session)
    authentication_db.scalar.return_value = user

    result = authenticate_user(
        authentication_db,
        email="  ADA@EXAMPLE.COM ",
        password="plain-secret",
    )

    assert result is user


def test_profile_update_applies_only_supplied_target_fields() -> None:
    db = MagicMock(spec=Session)
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        hashed_password="hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
    )

    result = update_user_profile(
        db,
        user=user,
        user_in=UserUpdate(first_name="Augusta", timezone="Europe/London"),
    )

    assert result is user
    assert user.first_name == "Augusta"
    assert user.last_name == "Lovelace"
    assert user.email == "ada@example.com"
    assert user.timezone == "Europe/London"
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
