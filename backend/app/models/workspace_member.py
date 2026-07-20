import uuid
import enum

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base


class WorkspaceRole(enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class WorkspaceMember(Base):

    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    workspace_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id"),
    )

    user_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    role = mapped_column(
        Enum(WorkspaceRole),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )

    workspace = relationship(
        "Workspace",
        back_populates="members",
    )

    user = relationship("User")