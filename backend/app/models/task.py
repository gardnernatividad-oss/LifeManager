from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.master_task import MasterTask
    from app.models.user import User
    from app.models.workspace import Workspace


class TaskResult(str, enum.Enum):
    COMPLETED = "COMPLETED"
    NOT_COMPLETED = "NOT_COMPLETED"


class Task(BaseEntity):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["master_task_id", "workspace_id"], ["master_tasks.id", "master_tasks.workspace_id"],
            name="fk_tasks_master_task_workspace", ondelete="RESTRICT"
        ),
        UniqueConstraint(
            "workspace_id", "master_task_id", "planned_date",
            name="uq_tasks_workspace_id_master_task_id_planned_date"
        ),
        CheckConstraint("result IS NULL OR result IN ('COMPLETED', 'NOT_COMPLETED')", name="ck_tasks_result_valid"),
        CheckConstraint(
            "(result IS NULL AND resolved_at IS NULL AND resolved_by_id IS NULL) OR "
            "(result IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_tasks_resolution_consistent",
        ),
        CheckConstraint("lock_version > 0", name="ck_tasks_lock_version_positive"),
        Index("ix_tasks_workspace_id_planned_date_id", "workspace_id", text("planned_date DESC"), "id"),
        Index("ix_tasks_workspace_id_result_planned_date", "workspace_id", "result", text("planned_date DESC")),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    master_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[TaskResult | None] = mapped_column(String(20), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="tasks", overlaps="master_task,tasks"
    )
    master_task: Mapped[MasterTask] = relationship(
        "MasterTask", back_populates="tasks", overlaps="tasks,workspace"
    )
    created_by: Mapped[User | None] = relationship(
        "User", back_populates="created_tasks", foreign_keys=[created_by_id]
    )
    resolved_by: Mapped[User | None] = relationship(
        "User", back_populates="resolved_tasks", foreign_keys=[resolved_by_id]
    )
