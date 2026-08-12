from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.task import Task
    from app.models.workspace import Workspace


class MasterTask(BaseEntity):
    __tablename__ = "master_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"],
            name="fk_master_tasks_category_workspace", ondelete="RESTRICT"
        ),
        UniqueConstraint("workspace_id", "normalized_name", name="uq_master_tasks_workspace_id_normalized_name"),
        UniqueConstraint("id", "workspace_id", name="uq_master_tasks_id_workspace_id"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_master_tasks_name_not_blank"),
        Index("ix_master_tasks_workspace_id_category_id_name", "workspace_id", "category_id", "name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="master_tasks", overlaps="category,master_tasks"
    )
    category: Mapped[Category] = relationship(
        "Category", back_populates="master_tasks", overlaps="master_tasks,workspace"
    )
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="master_task")
