"""Cascade Pending Item history when its eligible parent is deleted.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from collections.abc import Sequence

from alembic import op


revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_pending_item_history_item_workspace",
        "pending_item_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pending_item_history_item_workspace",
        "pending_item_history",
        "pending_items",
        ["pending_item_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_pending_item_history_item_workspace",
        "pending_item_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pending_item_history_item_workspace",
        "pending_item_history",
        "pending_items",
        ["pending_item_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
