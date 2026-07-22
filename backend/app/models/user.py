from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.daily_form import DailyFormSubmission
    from app.models.task import Task
    from app.models.task_series import TaskSeries
    from app.models.workspace_member import WorkspaceMember


class User(BaseEntity):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    email: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="America/Lima",
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="es-PE",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    workspace_members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="user",
    )

    created_tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="created_by",
    )

    created_task_series: Mapped[list["TaskSeries"]] = relationship(
        "TaskSeries",
        back_populates="created_by",
    )

    daily_form_submissions: Mapped[list["DailyFormSubmission"]] = relationship(
        "DailyFormSubmission", back_populates="user",
    )
