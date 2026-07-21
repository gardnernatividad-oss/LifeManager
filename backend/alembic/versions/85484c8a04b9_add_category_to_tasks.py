"""add category to tasks

Revision ID: 85484c8a04b9
Revises: 25776ea3a156
Create Date: 2026-07-20 23:02:47.139350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85484c8a04b9'
down_revision: Union[str, Sequence[str], None] = '25776ea3a156'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tasks",
        sa.Column("category_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tasks_category_id_categories",
        "tasks",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tasks_workspace_id_category_id",
        "tasks",
        ["workspace_id", "category_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tasks_workspace_id_category_id",
        table_name="tasks",
    )
    op.drop_constraint(
        "fk_tasks_category_id_categories",
        "tasks",
        type_="foreignkey",
    )
    op.drop_column("tasks", "category_id")
