import enum
import uuid

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.project import Project
    from app.models.task_series import TaskSeries
    from app.models.user import User
    from app.models.workspace import Workspace


class TaskOutcome(str, enum.Enum):
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    PENDING = "pending"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class Task(BaseEntity):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "(outcome IS NULL AND resolved_at IS NULL) OR "
            "(outcome IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_tasks_outcome_resolved_at_consistent",
        ),
        Index(
            "ix_tasks_workspace_id_outcome_scheduled_at",
            "workspace_id",
            "outcome",
            "scheduled_at",
        ),
        Index("ix_tasks_workspace_id_category_id", "workspace_id", "category_id"),
        Index("ix_tasks_workspace_id_project_id", "workspace_id", "project_id"),
        UniqueConstraint(
            "task_series_id",
            "scheduled_at",
            name="uq_tasks_task_series_id_scheduled_at",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[TaskOutcome | None] = mapped_column(
        Enum(
            TaskOutcome,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            name="taskoutcome",
        ),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="tasks")
    created_by: Mapped["User"] = relationship("User", back_populates="created_tasks")
    category: Mapped["Category | None"] = relationship("Category", back_populates="tasks")
    project: Mapped["Project | None"] = relationship("Project", back_populates="tasks")
    task_series: Mapped["TaskSeries | None"] = relationship("TaskSeries", back_populates="tasks")
