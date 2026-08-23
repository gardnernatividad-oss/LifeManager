import uuid

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserAccountStateEvent, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    MembershipStatus,
    WorkspaceKind,
)
from app.schemas.v2_identity import RegistrationRequestCreate


class RegistrationRequestConflictError(ValueError):
    pass


class AdminAccountNotFoundError(ValueError):
    pass


class AccountStateConflictError(ValueError):
    pass


class PersonalWorkspaceConflictError(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[AccountStatus, frozenset[AccountStatus]] = {
    AccountStatus.PENDING_EMAIL_VERIFICATION: frozenset(
        {AccountStatus.PENDING_APPROVAL}
    ),
    AccountStatus.PENDING_APPROVAL: frozenset(
        {AccountStatus.ACTIVE, AccountStatus.REJECTED}
    ),
    AccountStatus.ACTIVE: frozenset({AccountStatus.DISABLED}),
    AccountStatus.DISABLED: frozenset({AccountStatus.ACTIVE}),
    AccountStatus.REJECTED: frozenset(),
}


def is_account_usable(user: User) -> bool:
    return user.account_status == AccountStatus.ACTIVE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event(
    db: Session,
    *,
    user: User,
    previous_status: AccountStatus | None,
    new_status: AccountStatus,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
) -> UserAccountStateEvent:
    event = UserAccountStateEvent(
        user_id=user.id,
        from_status=previous_status,
        to_status=new_status,
        actor_user_id=actor_user_id,
        reason=reason,
        created_at=_now(),
    )
    db.add(event)
    return event


def transition_account_state(
    db: Session,
    *,
    user: User,
    new_status: AccountStatus,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
) -> UserAccountStateEvent:
    previous_status = AccountStatus(user.account_status)
    if new_status not in ALLOWED_TRANSITIONS[previous_status]:
        raise AccountStateConflictError("Account state transition is not allowed")
    if (
        new_status is not AccountStatus.PENDING_EMAIL_VERIFICATION
        and user.email_verified_at is None
    ):
        raise AccountStateConflictError("Verified email is required for this transition")

    user.account_status = new_status
    user.status_changed_at = _now()
    user.lock_version += 1
    return _event(
        db,
        user=user,
        previous_status=previous_status,
        new_status=new_status,
        actor_user_id=actor_user_id,
        reason=reason,
    )


def _is_registration_unique_violation(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == "uq_users_email"


def create_registration_request(
    db: Session,
    *,
    registration_in: RegistrationRequestCreate,
) -> User:
    normalized_email = str(registration_in.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise RegistrationRequestConflictError("Registration request cannot be created")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(registration_in.password),
        first_name=registration_in.first_name,
        last_name=registration_in.last_name,
        timezone=registration_in.timezone,
        account_status=AccountStatus.PENDING_EMAIL_VERIFICATION,
        global_role=None,
        email_verified_at=None,
        status_changed_at=_now(),
    )
    db.add(user)
    try:
        db.flush()
        _event(
            db,
            user=user,
            previous_status=None,
            new_status=AccountStatus.PENDING_EMAIL_VERIFICATION,
            actor_user_id=None,
        )
        db.flush()
    except IntegrityError as error:
        if _is_registration_unique_violation(error):
            raise RegistrationRequestConflictError(
                "Registration request cannot be created"
            ) from error
        raise
    return user


def list_pending_registration_requests(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.account_status == AccountStatus.PENDING_APPROVAL)
            .order_by(User.created_at, User.id)
        ).all()
    )


def get_admin_account(db: Session, *, user_id: uuid.UUID) -> User:
    user = db.scalar(
        select(User).where(
            User.id == user_id,
            User.account_status == AccountStatus.PENDING_APPROVAL,
        )
    )
    if user is None:
        raise AdminAccountNotFoundError("Account not found")
    return user


def _lock_admin_target(db: Session, *, user_id: uuid.UUID) -> User:
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise AdminAccountNotFoundError("Account not found")
    return user


def approve_registration_request(
    db: Session,
    *,
    user_id: uuid.UUID,
    actor: User,
) -> User:
    user = _lock_admin_target(db, user_id=user_id)
    if user.account_status != AccountStatus.PENDING_APPROVAL:
        raise AccountStateConflictError("Account is not pending approval")

    existing_workspace = db.scalar(
        select(Workspace.id)
        .where(
            Workspace.owner_user_id == user.id,
            Workspace.kind == WorkspaceKind.PERSONAL,
        )
        .with_for_update()
    )
    if existing_workspace is not None:
        raise PersonalWorkspaceConflictError("Personal workspace already exists")

    transition_account_state(
        db,
        user=user,
        new_status=AccountStatus.ACTIVE,
        actor_user_id=actor.id,
        reason="GLOBAL_ADMIN_APPROVAL",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Personal",
        kind=WorkspaceKind.PERSONAL,
        owner_user_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            status=MembershipStatus.ACTIVE,
            calendar_visibility=CalendarVisibility.HIDE,
        )
    )
    db.flush()
    return user


def reject_registration_request(
    db: Session,
    *,
    user_id: uuid.UUID,
    actor: User,
    reason: str | None,
) -> User:
    user = _lock_admin_target(db, user_id=user_id)
    if user.account_status != AccountStatus.PENDING_APPROVAL:
        raise AccountStateConflictError("Account is not pending approval")
    transition_account_state(
        db,
        user=user,
        new_status=AccountStatus.REJECTED,
        actor_user_id=actor.id,
        reason=reason or "GLOBAL_ADMIN_REJECTION",
    )
    db.flush()
    return user
