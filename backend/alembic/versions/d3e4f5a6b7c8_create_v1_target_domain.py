"""Create the LifeManager V1 target domain.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "categories",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_categories_name_not_blank"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_categories_workspace_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_categories_id_workspace_id"),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_categories_workspace_id_normalized_name"),
    )

    op.create_table(
        "master_tasks",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("normalized_name", sa.String(length=150), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_master_tasks_name_not_blank"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_master_tasks_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_master_tasks_category_workspace", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_master_tasks"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_master_tasks_id_workspace_id"),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_master_tasks_workspace_id_normalized_name"),
    )
    op.create_index("ix_master_tasks_workspace_id_category_id_name", "master_tasks", ["workspace_id", "category_id", "name"], unique=False)

    op.create_table(
        "tasks",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("result IS NULL OR result IN ('COMPLETED', 'NOT_COMPLETED')", name="ck_tasks_result_valid"),
        sa.CheckConstraint("(result IS NULL AND resolved_at IS NULL AND resolved_by_id IS NULL) OR (result IS NOT NULL AND resolved_at IS NOT NULL)", name="ck_tasks_resolution_consistent"),
        sa.CheckConstraint("lock_version > 0", name="ck_tasks_lock_version_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_tasks_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_task_id", "workspace_id"], ["master_tasks.id", "master_tasks.workspace_id"], name="fk_tasks_master_task_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], name="fk_tasks_resolved_by_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_tasks_created_by_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
        sa.UniqueConstraint("workspace_id", "master_task_id", "planned_date", name="uq_tasks_workspace_id_master_task_id_planned_date"),
    )
    op.create_index("ix_tasks_workspace_id_planned_date_id", "tasks", ["workspace_id", sa.text("planned_date DESC"), "id"], unique=False)
    op.create_index("ix_tasks_workspace_id_result_planned_date", "tasks", ["workspace_id", "result", sa.text("planned_date DESC")], unique=False)

    op.create_table(
        "pending_items",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("progress", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_pending_items_name_not_blank"),
        sa.CheckConstraint("NOT is_active OR planned_date IS NOT NULL", name="ck_pending_items_active_requires_planned_date"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_pending_items_progress_range"),
        sa.CheckConstraint("(progress = 100 AND completion_date IS NOT NULL) OR (progress < 100 AND completion_date IS NULL)", name="ck_pending_items_completion_consistent"),
        sa.CheckConstraint("lock_version > 0", name="ck_pending_items_lock_version_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_pending_items_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_pending_items_category_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_pending_items_created_by_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pending_items"),
    )
    op.create_index("ix_pending_items_workspace_id_is_active_planned_date_id", "pending_items", ["workspace_id", "is_active", "planned_date", "id"], unique=False)
    op.create_index("ix_pending_items_workspace_id_category_id_planned_date", "pending_items", ["workspace_id", "category_id", "planned_date"], unique=False)

    op.create_table(
        "projects",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("general_comment", sa.Text(), nullable=True),
        sa.Column("last_tracking_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name_not_blank"),
        sa.CheckConstraint("lock_version > 0", name="ck_projects_lock_version_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_projects_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_projects_category_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_projects_created_by_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index("ix_projects_workspace_id_is_active_category_id_name", "projects", ["workspace_id", "is_active", "category_id", "name"], unique=False)

    op.create_table(
        "project_steps",
        *_audit_columns(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("progress", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_project_steps_name_not_blank"),
        sa.CheckConstraint("weight IS NULL OR (weight > 0 AND weight <= 100)", name="ck_project_steps_weight_range"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_project_steps_progress_range"),
        sa.CheckConstraint("(progress = 100 AND completion_date IS NOT NULL) OR (progress < 100 AND completion_date IS NULL)", name="ck_project_steps_completion_consistent"),
        sa.CheckConstraint("position >= 0", name="ck_project_steps_position_nonnegative"),
        sa.CheckConstraint("lock_version > 0", name="ck_project_steps_lock_version_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_steps_project_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_steps"),
        sa.UniqueConstraint("project_id", "position", name="uq_project_steps_project_id_position"),
    )
    op.create_index("ix_project_steps_planned_date_progress_project_id", "project_steps", ["planned_date", "progress", "project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_steps_planned_date_progress_project_id", table_name="project_steps")
    op.drop_table("project_steps")
    op.drop_index("ix_projects_workspace_id_is_active_category_id_name", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_pending_items_workspace_id_category_id_planned_date", table_name="pending_items")
    op.drop_index("ix_pending_items_workspace_id_is_active_planned_date_id", table_name="pending_items")
    op.drop_table("pending_items")
    op.drop_index("ix_tasks_workspace_id_result_planned_date", table_name="tasks")
    op.drop_index("ix_tasks_workspace_id_planned_date_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_master_tasks_workspace_id_category_id_name", table_name="master_tasks")
    op.drop_table("master_tasks")
    op.drop_table("categories")
