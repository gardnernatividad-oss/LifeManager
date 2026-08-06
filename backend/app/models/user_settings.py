import enum
import uuid

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.user import User


class WeekStartsOn(str, enum.Enum):
    MONDAY = "MONDAY"
    SUNDAY = "SUNDAY"


class UserSettings(BaseEntity):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        CheckConstraint("length(btrim(timezone)) > 0", name="ck_user_settings_timezone_not_blank"),
        CheckConstraint("length(btrim(locale)) > 0", name="ck_user_settings_locale_not_blank"),
        CheckConstraint("task_due_reminder_minutes BETWEEN 0 AND 1440", name="ck_user_settings_task_due_minutes_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(100), default="America/Lima", server_default=text("'America/Lima'"), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="es-PE", server_default=text("'es-PE'"), nullable=False)
    week_starts_on: Mapped[WeekStartsOn] = mapped_column(
        Enum(WeekStartsOn, values_callable=lambda enum_type: [item.value for item in enum_type], name="weekstartson"),
        default=WeekStartsOn.MONDAY, server_default=text("'MONDAY'"), nullable=False,
    )
    daily_form_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    task_due_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    task_overdue_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    daily_form_reminder_time: Mapped[time] = mapped_column(Time(timezone=False), default=time(9), server_default=text("'09:00:00'"), nullable=False)
    task_due_reminder_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default=text("60"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="settings")
