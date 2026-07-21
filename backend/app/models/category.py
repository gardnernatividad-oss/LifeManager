import uuid

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Category(BaseEntity):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "normalized_name",
            name="uq_categories_workspace_id_normalized_name",
        ),
        CheckConstraint(
            "length(btrim(name)) > 0",
            name="ck_categories_name_not_blank",
        ),
        Index(
            "ix_categories_workspace_id_is_active_name",
            "workspace_id",
            "is_active",
            "name",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    normalized_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="categories",
    )
