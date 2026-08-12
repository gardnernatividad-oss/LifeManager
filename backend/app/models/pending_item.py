from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User
    from app.models.workspace import Workspace


class PendingItem(BaseEntity):
    __tablename__ = "pending_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"],
            name="fk_pending_items_category_workspace", ondelete="RESTRICT"
        ),
        CheckConstraint("length(btrim(name)) > 0", name="ck_pending_items_name_not_blank"),
        CheckConstraint("NOT is_active OR planned_date IS NOT NULL", name="ck_pending_items_active_requires_planned_date"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_pending_items_progress_range"),
        CheckConstraint(
            "(progress = 100 AND completion_date IS NOT NULL) OR "
            "(progress < 100 AND completion_date IS NULL)",
            name="ck_pending_items_completion_consistent",
        ),
        CheckConstraint("lock_version > 0", name="ck_pending_items_lock_version_positive"),
        Index("ix_pending_items_workspace_id_is_active_planned_date_id", "workspace_id", "is_active", "planned_date", "id"),
        Index("ix_pending_items_workspace_id_category_id_planned_date", "workspace_id", "category_id", "planned_date"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="pending_items", overlaps="category,pending_items"
    )
    category: Mapped[Category] = relationship(
        "Category", back_populates="pending_items", overlaps="pending_items,workspace"
    )
    created_by: Mapped[User | None] = relationship("User", back_populates="created_pending_items")
