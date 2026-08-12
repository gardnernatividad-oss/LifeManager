from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.project_step import ProjectStep
    from app.models.user import User
    from app.models.workspace import Workspace


class Project(BaseEntity):
    __tablename__ = "projects"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"],
            name="fk_projects_category_workspace", ondelete="RESTRICT"
        ),
        CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name_not_blank"),
        CheckConstraint("lock_version > 0", name="ck_projects_lock_version_positive"),
        Index("ix_projects_workspace_id_is_active_category_id_name", "workspace_id", "is_active", "category_id", "name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    general_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tracking_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="projects", overlaps="category,projects"
    )
    category: Mapped[Category] = relationship(
        "Category", back_populates="projects", overlaps="projects,workspace"
    )
    created_by: Mapped[User | None] = relationship("User", back_populates="created_projects")
    steps: Mapped[list[ProjectStep]] = relationship(
        "ProjectStep", back_populates="project", order_by="ProjectStep.position"
    )
