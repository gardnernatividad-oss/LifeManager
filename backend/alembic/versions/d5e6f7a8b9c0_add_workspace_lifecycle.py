"""add workspace lifecycle

Revision ID: d5e6f7a8b9c0
Revises: c3d172b18308
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c3d172b18308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "lifecycle",
            sa.String(length=16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_workspaces_lifecycle_valid",
        "workspaces",
        "lifecycle IN ('ACTIVE','INACTIVE')",
    )
    op.create_check_constraint(
        "ck_workspaces_lifecycle_consistent",
        "workspaces",
        "(lifecycle = 'ACTIVE' AND deactivated_at IS NULL) OR "
        "(lifecycle = 'INACTIVE' AND deactivated_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_workspaces_personal_active",
        "workspaces",
        "kind = 'SHARED' OR lifecycle = 'ACTIVE'",
    )
    op.create_index(
        "ix_workspaces_owner_lifecycle_kind_id",
        "workspaces",
        ["owner_user_id", "lifecycle", "kind", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspaces_owner_lifecycle_kind_id", table_name="workspaces")
    op.drop_constraint("ck_workspaces_personal_active", "workspaces", type_="check")
    op.drop_constraint("ck_workspaces_lifecycle_consistent", "workspaces", type_="check")
    op.drop_constraint("ck_workspaces_lifecycle_valid", "workspaces", type_="check")
    op.drop_column("workspaces", "deactivated_at")
    op.drop_column("workspaces", "lifecycle")
