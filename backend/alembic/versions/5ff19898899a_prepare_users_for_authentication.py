"""prepare users for authentication

Revision ID: 5ff19898899a
Revises: 813f6ce3a35b
Create Date: 2026-07-20 17:20:33.546371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ff19898899a'
down_revision: Union[str, Sequence[str], None] = '813f6ce3a35b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "users",
        "password_hash",
        new_column_name="hashed_password",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(length=100), nullable=True),
    )
    op.execute(
        "UPDATE users "
        "SET first_name = LEFT(full_name, 100), last_name = ''"
    )
    op.alter_column("users", "first_name", nullable=False)
    op.alter_column("users", "last_name", nullable=False)
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.alter_column(
        "users",
        "hashed_password",
        new_column_name="password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")
