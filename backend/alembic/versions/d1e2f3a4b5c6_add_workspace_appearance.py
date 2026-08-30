"""Add safe persisted Workspace appearance.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("color", sa.String(length=16), nullable=True))
    op.add_column("workspaces", sa.Column("icon", sa.String(length=16), nullable=True))
    op.execute("UPDATE workspaces SET color = CASE WHEN kind = 'PERSONAL' THEN 'GREEN' ELSE 'BLUE' END")
    op.execute("UPDATE workspaces SET icon = CASE WHEN kind = 'PERSONAL' THEN 'HOME' ELSE 'USERS' END")
    op.alter_column("workspaces", "color", nullable=False, server_default=sa.text("'GREEN'"))
    op.alter_column("workspaces", "icon", nullable=False, server_default=sa.text("'HOME'"))
    op.create_check_constraint(
        "ck_workspaces_color_valid", "workspaces",
        "color IN ('GREEN','BLUE','PURPLE','ORANGE','RED','TEAL')",
    )
    op.create_check_constraint(
        "ck_workspaces_icon_valid", "workspaces",
        "icon IN ('HOME','USERS','HEART','STAR','CALENDAR','BRIEFCASE')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workspaces_icon_valid", "workspaces", type_="check")
    op.drop_constraint("ck_workspaces_color_valid", "workspaces", type_="check")
    op.drop_column("workspaces", "icon")
    op.drop_column("workspaces", "color")
