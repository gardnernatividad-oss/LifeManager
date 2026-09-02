import math
import uuid

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import AccountStatus, GlobalRole
from app.services.v2_identity import (
    AccountStateConflictError,
    AdminAccountNotFoundError,
    transition_account_state,
)


@dataclass(frozen=True)
class AdminUserPage:
    items: list[User]
    total: int
    page: int
    page_size: int
    total_pages: int


def list_admin_users(
    db: Session,
    *,
    page: int,
    page_size: int,
    account_status: AccountStatus | None,
    search: str | None,
) -> AdminUserPage:
    filters = []
    if account_status is not None:
        filters.append(User.account_status == account_status)
    cleaned = search.strip() if search else ""
    if cleaned:
        escaped = cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        filters.append(
            or_(
                User.email.ilike(pattern, escape="\\"),
                User.first_name.ilike(pattern, escape="\\"),
                User.last_name.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    items = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return AdminUserPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


def get_admin_user(db: Session, *, user_id: uuid.UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise AdminAccountNotFoundError("Account not found")
    return user


def change_admin_account_state(
    db: Session,
    *,
    user_id: uuid.UUID,
    expected_lock_version: int,
    new_status: AccountStatus,
    actor: User,
    reason: str | None,
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AdminAccountNotFoundError("Account not found")
    if user.lock_version != expected_lock_version:
        raise AccountStateConflictError("Account changed concurrently")
    if user.global_role == GlobalRole.GLOBAL_ADMIN:
        raise AccountStateConflictError("Global administrator state is operationally protected")
    transition_account_state(
        db,
        user=user,
        new_status=new_status,
        actor_user_id=actor.id,
        reason=reason or f"GLOBAL_ADMIN_{new_status.value}",
    )
    db.flush()
    return user
