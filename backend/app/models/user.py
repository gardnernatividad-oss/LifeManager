from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.pending_item import PendingItem
    from app.models.project import Project
    from app.models.task import Task
    from app.models.workspace_member import WorkspaceMember


class User(BaseEntity):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(btrim(first_name)) > 0", name="ck_users_first_name_not_blank"),
        CheckConstraint("length(btrim(last_name)) > 0", name="ck_users_last_name_not_blank"),
        CheckConstraint("length(btrim(timezone)) > 0", name="ck_users_timezone_not_blank"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(100), default="America/Lima", server_default=text("'America/Lima'"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    workspace_members: Mapped[list[WorkspaceMember]] = relationship(
        "WorkspaceMember", back_populates="user"
    )
    created_tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="created_by", foreign_keys="Task.created_by_id"
    )
    resolved_tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="resolved_by", foreign_keys="Task.resolved_by_id"
    )
    created_pending_items: Mapped[list[PendingItem]] = relationship(
        "PendingItem", back_populates="created_by"
    )
    created_projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="created_by"
    )
