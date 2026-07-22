"""link tasks to task series

Revision ID: a7d0e3f5c824
Revises: f6c9d2e4b713
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d0e3f5c824"
down_revision: Union[str, Sequence[str], None] = "f6c9d2e4b713"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("task_series_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_task_series_id_task_series",
        "tasks", "task_series", ["task_series_id"], ["id"], ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_tasks_task_series_id_scheduled_at",
        "tasks", ["task_series_id", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tasks_task_series_id_scheduled_at", "tasks", type_="unique")
    op.drop_constraint("fk_tasks_task_series_id_task_series", "tasks", type_="foreignkey")
    op.drop_column("tasks", "task_series_id")
