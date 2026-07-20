import enum
import uuid

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Workspace


class WorkspaceRole(enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class WorkspaceMember(BaseEntity):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            name="uq_workspace_members_user_id_workspace_id",
        ),
        Index("ix_workspace_members_user_id", "user_id"),
        Index("ix_workspace_members_workspace_id", "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="workspace_members",
    )
