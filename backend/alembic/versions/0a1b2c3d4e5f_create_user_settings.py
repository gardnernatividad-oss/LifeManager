"""create user settings

Revision ID: 0a1b2c3d4e5f
Revises: f7a0b1c2d3e4
Create Date: 2026-07-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f7a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
week_starts_on_enum = postgresql.ENUM("MONDAY", "SUNDAY", name="weekstartson", create_type=False)


def upgrade() -> None:
    week_starts_on_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("timezone", sa.String(100), server_default="America/Lima", nullable=False),
        sa.Column("locale", sa.String(20), server_default="es-PE", nullable=False),
        sa.Column("week_starts_on", week_starts_on_enum, server_default="MONDAY", nullable=False),
        sa.Column("daily_form_reminders_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("task_due_reminders_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("task_overdue_reminders_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("daily_form_reminder_time", sa.Time(timezone=False), server_default="09:00:00", nullable=False),
        sa.Column("task_due_reminder_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(timezone)) > 0", name="ck_user_settings_timezone_not_blank"),
        sa.CheckConstraint("length(btrim(locale)) > 0", name="ck_user_settings_locale_not_blank"),
        sa.CheckConstraint("task_due_reminder_minutes BETWEEN 0 AND 1440", name="ck_user_settings_task_due_minutes_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_settings_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_settings"),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    week_starts_on_enum.drop(op.get_bind(), checkfirst=True)
