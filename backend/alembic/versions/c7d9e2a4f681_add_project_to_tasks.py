"""add project to tasks

Revision ID: c7d9e2a4f681
Revises: b3a41f2c9d70
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d9e2a4f681"
down_revision: Union[str, Sequence[str], None] = "b3a41f2c9d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("project_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_project_id_projects",
        "tasks",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tasks_workspace_id_project_id",
        "tasks",
        ["workspace_id", "project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_workspace_id_project_id", table_name="tasks")
    op.drop_constraint("fk_tasks_project_id_projects", "tasks", type_="foreignkey")
    op.drop_column("tasks", "project_id")
