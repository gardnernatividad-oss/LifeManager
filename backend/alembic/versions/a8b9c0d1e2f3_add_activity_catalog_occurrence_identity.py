"""Add the catalog Activity occurrence identity.

Revision ID: a8b9c0d1e2f3
Revises: e6f7a8b9c0d1
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_activities_catalog_occurrence",
        "activities",
        ["workspace_id", "activity_master_id", "organizer_user_id", "starts_at"],
        unique=True,
        postgresql_where=sa.text("activity_master_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_activities_catalog_occurrence", table_name="activities")
