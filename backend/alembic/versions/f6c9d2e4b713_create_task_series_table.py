"""create task series table

Revision ID: f6c9d2e4b713
Revises: e5b8c1d3a902
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6c9d2e4b713"
down_revision: Union[str, Sequence[str], None] = "e5b8c1d3a902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

frequency_enum = postgresql.ENUM("daily", "weekly", "monthly", name="taskseriesfrequency", create_type=False)


def upgrade() -> None:
    frequency_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "task_series",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("frequency", frequency_enum, nullable=False),
        sa.Column("interval", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("month_day", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_task_series_title_not_blank"),
        sa.CheckConstraint("interval BETWEEN 1 AND 365", name="ck_task_series_interval_range"),
        sa.CheckConstraint("(frequency = 'daily' AND weekdays IS NULL AND month_day IS NULL) OR (frequency = 'weekly' AND weekdays IS NOT NULL AND cardinality(weekdays) > 0 AND month_day IS NULL) OR (frequency = 'monthly' AND weekdays IS NULL AND month_day BETWEEN 1 AND 31)", name="ck_task_series_recurrence_shape"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_task_series_end_after_start"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_task_series_workspace_id_workspaces", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_task_series_created_by_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_task_series_category_id_categories", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_task_series_project_id_projects", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_task_series"),
    )
    op.create_index("ix_task_series_workspace_id_is_active_title", "task_series", ["workspace_id", "is_active", "title"], unique=False)
    op.create_index("ix_task_series_is_active_starts_at", "task_series", ["is_active", "starts_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_series_is_active_starts_at", table_name="task_series")
    op.drop_index("ix_task_series_workspace_id_is_active_title", table_name="task_series")
    op.drop_table("task_series")
    frequency_enum.drop(op.get_bind(), checkfirst=True)
