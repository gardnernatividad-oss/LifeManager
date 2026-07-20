"""create tasks table

Revision ID: 6fc7f7599458
Revises: 5ff19898899a
Create Date: 2026-07-20 18:31:29.818952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6fc7f7599458'
down_revision: Union[str, Sequence[str], None] = '5ff19898899a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_status_enum = postgresql.ENUM(
    "todo",
    "in_progress",
    "done",
    "canceled",
    name="taskstatus",
    create_type=False,
)

task_priority_enum = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "urgent",
    name="taskpriority",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    task_status_enum.create(op.get_bind(), checkfirst=True)
    task_priority_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tasks",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            task_status_enum,
            server_default=sa.text("'todo'::taskstatus"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            task_priority_enum,
            server_default=sa.text("'medium'::taskpriority"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tasks_created_by_id",
        "tasks",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_due_at",
        "tasks",
        ["due_at"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_workspace_id",
        "tasks",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_workspace_id_status_position",
        "tasks",
        ["workspace_id", "status", "position"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tasks_workspace_id_status_position",
        table_name="tasks",
    )
    op.drop_index("ix_tasks_workspace_id", table_name="tasks")
    op.drop_index("ix_tasks_due_at", table_name="tasks")
    op.drop_index("ix_tasks_created_by_id", table_name="tasks")
    op.drop_table("tasks")
    task_priority_enum.drop(op.get_bind(), checkfirst=True)
    task_status_enum.drop(op.get_bind(), checkfirst=True)
