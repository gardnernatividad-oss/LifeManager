"""finalize manual task contract

Revision ID: e5b8c1d3a902
Revises: c7d9e2a4f681
Create Date: 2026-07-20

Downgrade maps NOT_COMPLETED to legacy TODO because the legacy schema has no
equivalent terminal status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5b8c1d3a902"
down_revision: Union[str, Sequence[str], None] = "c7d9e2a4f681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_outcome_enum = postgresql.ENUM(
    "completed", "not_completed", "cancelled",
    name="taskoutcome", create_type=False,
)
legacy_status_enum = postgresql.ENUM(
    "todo", "in_progress", "done", "canceled",
    name="taskstatus", create_type=False,
)
legacy_priority_enum = postgresql.ENUM(
    "low", "medium", "high", "urgent",
    name="taskpriority", create_type=False,
)


def upgrade() -> None:
    task_outcome_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("tasks", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("outcome", task_outcome_enum, nullable=True))
    op.add_column("tasks", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE tasks
        SET scheduled_at = COALESCE(due_at, created_at),
            outcome = CASE
                WHEN status = 'done'::taskstatus THEN 'completed'::taskoutcome
                WHEN status = 'canceled'::taskstatus THEN 'cancelled'::taskoutcome
                WHEN is_archived THEN 'cancelled'::taskoutcome
                ELSE NULL
            END,
            resolved_at = CASE
                WHEN status IN ('done'::taskstatus, 'canceled'::taskstatus)
                    THEN COALESCE(completed_at, updated_at, created_at)
                WHEN is_archived
                    THEN COALESCE(updated_at, created_at)
                ELSE NULL
            END
        """
    )
    op.alter_column("tasks", "scheduled_at", nullable=False)

    op.drop_index("ix_tasks_workspace_id_status_position", table_name="tasks")
    op.drop_index("ix_tasks_due_at", table_name="tasks")
    op.drop_column("tasks", "status")
    op.drop_column("tasks", "priority")
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "position")
    op.drop_column("tasks", "is_archived")
    legacy_priority_enum.drop(op.get_bind(), checkfirst=True)
    legacy_status_enum.drop(op.get_bind(), checkfirst=True)

    op.create_check_constraint(
        "ck_tasks_outcome_resolved_at_consistent",
        "tasks",
        "(outcome IS NULL AND resolved_at IS NULL) OR "
        "(outcome IS NOT NULL AND resolved_at IS NOT NULL)",
    )
    op.create_index(
        "ix_tasks_workspace_id_outcome_scheduled_at",
        "tasks",
        ["workspace_id", "outcome", "scheduled_at"],
        unique=False,
    )


def downgrade() -> None:
    legacy_status_enum.create(op.get_bind(), checkfirst=True)
    legacy_priority_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tasks",
        sa.Column(
            "status", legacy_status_enum,
            server_default=sa.text("'todo'::taskstatus"), nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "priority", legacy_priority_enum,
            server_default=sa.text("'medium'::taskpriority"), nullable=False,
        ),
    )
    op.add_column("tasks", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("tasks", sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.execute(
        """
        UPDATE tasks
        SET status = CASE
                WHEN outcome = 'completed'::taskoutcome THEN 'done'::taskstatus
                WHEN outcome = 'cancelled'::taskoutcome THEN 'canceled'::taskstatus
                ELSE 'todo'::taskstatus
            END,
            due_at = scheduled_at,
            completed_at = CASE
                WHEN outcome = 'completed'::taskoutcome THEN resolved_at
                ELSE NULL
            END
        """
    )

    op.drop_index("ix_tasks_workspace_id_outcome_scheduled_at", table_name="tasks")
    op.drop_constraint("ck_tasks_outcome_resolved_at_consistent", "tasks", type_="check")
    op.create_index("ix_tasks_due_at", "tasks", ["due_at"], unique=False)
    op.create_index(
        "ix_tasks_workspace_id_status_position",
        "tasks", ["workspace_id", "status", "position"], unique=False,
    )
    op.drop_column("tasks", "outcome")
    op.drop_column("tasks", "resolved_at")
    op.drop_column("tasks", "scheduled_at")
    task_outcome_enum.drop(op.get_bind(), checkfirst=True)
