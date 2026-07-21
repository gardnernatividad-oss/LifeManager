"""create projects table

Revision ID: b3a41f2c9d70
Revises: 85484c8a04b9
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3a41f2c9d70"
down_revision: Union[str, Sequence[str], None] = "85484c8a04b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name_not_blank"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint(
            "workspace_id",
            "normalized_name",
            name="uq_projects_workspace_id_normalized_name",
        ),
    )
    op.create_index(
        "ix_projects_workspace_id_is_active_name",
        "projects",
        ["workspace_id", "is_active", "name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_projects_workspace_id_is_active_name", table_name="projects")
    op.drop_table("projects")
