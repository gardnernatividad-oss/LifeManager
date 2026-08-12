from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.master_task import MasterTask
    from app.models.pending_item import PendingItem
    from app.models.project import Project
    from app.models.task import Task
    from app.models.workspace_member import WorkspaceMember
    from app.models.workspace_tracking_metadata import WorkspaceTrackingMetadata


class WorkspaceKind(str, enum.Enum):
    PERSONAL = "PERSONAL"
    COLLABORATIVE = "COLLABORATIVE"


class Workspace(BaseEntity):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_workspaces_name_not_blank"),
        CheckConstraint(
            "kind IN ('PERSONAL', 'COLLABORATIVE')", name="ck_workspaces_kind_valid"
        ),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[WorkspaceKind] = mapped_column(
        String(20), default=WorkspaceKind.PERSONAL, server_default=text("'PERSONAL'"), nullable=False
    )

    members: Mapped[list[WorkspaceMember]] = relationship("WorkspaceMember", back_populates="workspace")
    tracking_metadata: Mapped[WorkspaceTrackingMetadata | None] = relationship(
        "WorkspaceTrackingMetadata", back_populates="workspace", uselist=False,
        cascade="all, delete-orphan", single_parent=True,
    )
    categories: Mapped[list[Category]] = relationship("Category", back_populates="workspace")
    master_tasks: Mapped[list[MasterTask]] = relationship(
        "MasterTask", back_populates="workspace", overlaps="category,master_tasks"
    )
    tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="workspace", overlaps="master_task,tasks"
    )
    pending_items: Mapped[list[PendingItem]] = relationship(
        "PendingItem", back_populates="workspace", overlaps="category,pending_items"
    )
    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="workspace", overlaps="category,projects"
    )
