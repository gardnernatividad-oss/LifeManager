"""Add custom Task source and custom Activity identity.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b9c0d1e2f3a4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_tasks_workspace_master_date_responsible", "tasks", type_="unique")
    op.alter_column("tasks", "master_task_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("tasks", sa.Column("custom_name", sa.String(length=150), nullable=True))
    op.add_column("tasks", sa.Column("custom_category_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_custom_category_workspace", "tasks", "categories",
        ["custom_category_id", "workspace_id"], ["id", "workspace_id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_tasks_source_xor", "tasks",
        "(master_task_id IS NOT NULL AND custom_name IS NULL AND custom_category_id IS NULL) OR "
        "(master_task_id IS NULL AND custom_name IS NOT NULL AND custom_category_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_tasks_custom_name_not_blank", "tasks",
        "custom_name IS NULL OR length(btrim(custom_name)) > 0",
    )
    op.create_index(
        "uq_tasks_catalog_occurrence", "tasks",
        ["workspace_id", "master_task_id", "planned_date", "responsible_user_id"],
        unique=True, postgresql_where=sa.text("master_task_id IS NOT NULL"),
    )
    op.create_index(
        "uq_tasks_custom_occurrence", "tasks",
        ["workspace_id", "custom_name", "custom_category_id", "planned_date", "responsible_user_id"],
        unique=True, postgresql_where=sa.text("master_task_id IS NULL"),
    )
    op.create_index(
        "ix_tasks_workspace_custom_category_date", "tasks",
        ["workspace_id", "custom_category_id", sa.text("planned_date DESC")],
        postgresql_where=sa.text("custom_category_id IS NOT NULL"),
    )
    op.create_index(
        "uq_activities_custom_occurrence", "activities",
        ["workspace_id", "custom_category_id", "title", "organizer_user_id", "starts_at"],
        unique=True, postgresql_where=sa.text("activity_master_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_activities_custom_occurrence", table_name="activities")
    op.drop_index("ix_tasks_workspace_custom_category_date", table_name="tasks")
    op.drop_index("uq_tasks_custom_occurrence", table_name="tasks")
    op.drop_index("uq_tasks_catalog_occurrence", table_name="tasks")
    op.drop_constraint("ck_tasks_custom_name_not_blank", "tasks", type_="check")
    op.drop_constraint("ck_tasks_source_xor", "tasks", type_="check")
    op.drop_constraint("fk_tasks_custom_category_workspace", "tasks", type_="foreignkey")
    op.drop_column("tasks", "custom_category_id")
    op.drop_column("tasks", "custom_name")
    op.alter_column("tasks", "master_task_id", existing_type=sa.Uuid(), nullable=False)
    op.create_unique_constraint(
        "uq_tasks_workspace_master_date_responsible", "tasks",
        ["workspace_id", "master_task_id", "planned_date", "responsible_user_id"],
    )
