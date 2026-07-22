"""add workspace timezone

Revision ID: f7a0b1c2d3e4
Revises: e5f9a2b3c4d5
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e5f9a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("timezone", sa.String(length=100), server_default="America/Lima", nullable=False),
    )
    op.create_check_constraint(
        "ck_workspaces_timezone_not_blank",
        "workspaces",
        "length(btrim(timezone)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workspaces_timezone_not_blank", "workspaces", type_="check")
    op.drop_column("workspaces", "timezone")
