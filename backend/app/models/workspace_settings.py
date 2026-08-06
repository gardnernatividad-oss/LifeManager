import uuid

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.models.user_settings import WeekStartsOn

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceSettings(BaseEntity):
    __tablename__ = "workspace_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_settings_workspace_id"),
        CheckConstraint("length(btrim(timezone)) > 0", name="ck_workspace_settings_timezone_not_blank"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(100), default="America/Lima", server_default=text("'America/Lima'"), nullable=False)
    daily_form_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    daily_form_reminder_time: Mapped[time] = mapped_column(Time(timezone=False), default=time(9), server_default=text("'09:00:00'"), nullable=False)
    daily_task_generation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    week_starts_on: Mapped[WeekStartsOn] = mapped_column(
        Enum(WeekStartsOn, values_callable=lambda enum_type: [item.value for item in enum_type], name="weekstartson"),
        default=WeekStartsOn.MONDAY, server_default=text("'MONDAY'"), nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="settings")
