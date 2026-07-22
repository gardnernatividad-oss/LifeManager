import enum
import uuid

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.project import Project
    from app.models.task import Task
    from app.models.user import User
    from app.models.workspace import Workspace


class TaskSeriesFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskSeries(BaseEntity):
    __tablename__ = "task_series"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="ck_task_series_title_not_blank"),
        CheckConstraint("interval BETWEEN 1 AND 365", name="ck_task_series_interval_range"),
        CheckConstraint(
            "(frequency = 'daily' AND weekdays IS NULL AND month_day IS NULL) OR "
            "(frequency = 'weekly' AND weekdays IS NOT NULL AND cardinality(weekdays) > 0 AND month_day IS NULL) OR "
            "(frequency = 'monthly' AND weekdays IS NULL AND month_day BETWEEN 1 AND 31)",
            name="ck_task_series_recurrence_shape",
        ),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_task_series_end_after_start"),
        Index("ix_task_series_workspace_id_is_active_title", "workspace_id", "is_active", "title"),
        Index("ix_task_series_is_active_starts_at", "is_active", "starts_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[TaskSeriesFrequency] = mapped_column(
        Enum(TaskSeriesFrequency, values_callable=lambda enum_type: [item.value for item in enum_type], name="taskseriesfrequency"),
        nullable=False,
    )
    interval: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    month_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="task_series")
    created_by: Mapped["User"] = relationship("User", back_populates="created_task_series")
    category: Mapped["Category | None"] = relationship("Category", back_populates="task_series")
    project: Mapped["Project | None"] = relationship("Project", back_populates="task_series")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="task_series")
