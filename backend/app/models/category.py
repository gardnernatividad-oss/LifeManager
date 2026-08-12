from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.master_task import MasterTask
    from app.models.pending_item import PendingItem
    from app.models.project import Project
    from app.models.workspace import Workspace


class Category(BaseEntity):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "normalized_name", name="uq_categories_workspace_id_normalized_name"),
        UniqueConstraint("id", "workspace_id", name="uq_categories_id_workspace_id"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_categories_name_not_blank"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="categories")
    master_tasks: Mapped[list[MasterTask]] = relationship(
        "MasterTask", back_populates="category", overlaps="master_tasks,workspace"
    )
    pending_items: Mapped[list[PendingItem]] = relationship(
        "PendingItem", back_populates="category", overlaps="pending_items,workspace"
    )
    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="category", overlaps="projects,workspace"
    )
