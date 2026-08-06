"""create workspace settings

Revision ID: 1b2c3d4e5f60
Revises: 0a1b2c3d4e5f
Create Date: 2026-08-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "1b2c3d4e5f60"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
week_starts_on_enum = postgresql.ENUM("MONDAY", "SUNDAY", name="weekstartson", create_type=False)


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("timezone", sa.String(100), server_default="America/Lima", nullable=False),
        sa.Column("daily_form_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("daily_form_reminder_time", sa.Time(timezone=False), server_default="09:00:00", nullable=False),
        sa.Column("daily_task_generation_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("week_starts_on", week_starts_on_enum, server_default="MONDAY", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(timezone)) > 0", name="ck_workspace_settings_timezone_not_blank"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_settings_workspace_id_workspaces", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_settings"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_settings_workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("workspace_settings")
