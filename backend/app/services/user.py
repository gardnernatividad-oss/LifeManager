from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import (
    User,
    Workspace,
    WorkspaceKind,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceTrackingMetadata,
)
from app.schemas.user import UserCreate, UserUpdate


class EmailAlreadyRegisteredError(ValueError):
    pass


def _is_email_unique_violation(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    return constraint_name == "uq_users_email"


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User | None:
    normalized_email = str(email).strip().lower()
    statement = select(User).where(User.email == normalized_email)
    user = db.scalar(statement)

    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user


def register_user(
    db: Session,
    *,
    user_in: UserCreate,
) -> User:
    normalized_email = str(user_in.email).strip().lower()
    statement = select(User).where(User.email == normalized_email)
    if db.scalar(statement) is not None:
        raise EmailAlreadyRegisteredError("Email already registered")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        if _is_email_unique_violation(error):
            raise EmailAlreadyRegisteredError("Email already registered") from error
        raise

    workspace = Workspace(name="Personal", kind=WorkspaceKind.PERSONAL)
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRole.OWNER,
    )
    tracking_metadata = WorkspaceTrackingMetadata(workspace_id=workspace.id)
    db.add_all((membership, tracking_metadata))
    db.flush()

    return user


def update_user_profile(
    db: Session,
    *,
    user: User,
    user_in: UserUpdate,
) -> User:
    for field_name, value in user_in.model_dump(exclude_unset=True).items():
        setattr(user, field_name, value)
    db.flush()
    return user
