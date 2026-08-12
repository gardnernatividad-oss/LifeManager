from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectStep(BaseEntity):
    __tablename__ = "project_steps"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_project_steps_project_id_position"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_project_steps_name_not_blank"),
        CheckConstraint("weight IS NULL OR (weight > 0 AND weight <= 100)", name="ck_project_steps_weight_range"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_project_steps_progress_range"),
        CheckConstraint(
            "(progress = 100 AND completion_date IS NOT NULL) OR "
            "(progress < 100 AND completion_date IS NULL)",
            name="ck_project_steps_completion_consistent",
        ),
        CheckConstraint("position >= 0", name="ck_project_steps_position_nonnegative"),
        CheckConstraint("lock_version > 0", name="ck_project_steps_lock_version_positive"),
        Index("ix_project_steps_planned_date_progress_project_id", "planned_date", "progress", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="steps")
