from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.workspace_member import WorkspaceMember


class Workspace(BaseEntity):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="workspace",
    )
