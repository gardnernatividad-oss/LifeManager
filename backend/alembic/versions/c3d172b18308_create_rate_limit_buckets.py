"""create rate limit buckets

Revision ID: c3d172b18308
Revises: e4f5a6b7c8d9
Create Date: 2026-08-24 10:52:14.840247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d172b18308'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rate_limit_buckets",
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("dimension", sa.String(length=16), nullable=False),
        sa.Column("key_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempt_count", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(action)) > 0",
            name="ck_rate_limit_buckets_action_nonblank",
        ),
        sa.CheckConstraint(
            "length(btrim(dimension)) > 0",
            name="ck_rate_limit_buckets_dimension_nonblank",
        ),
        sa.CheckConstraint(
            "octet_length(key_digest) = 32",
            name="ck_rate_limit_buckets_digest_length",
        ),
        sa.CheckConstraint(
            "attempt_count >= 1",
            name="ck_rate_limit_buckets_attempt_count_positive",
        ),
        sa.CheckConstraint(
            "expires_at > window_start",
            name="ck_rate_limit_buckets_expiry_after_window",
        ),
        sa.PrimaryKeyConstraint(
            "action",
            "dimension",
            "key_digest",
            "window_start",
            name="pk_rate_limit_buckets",
        ),
    )
    op.create_index(
        "ix_rate_limit_buckets_expires_at",
        "rate_limit_buckets",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_rate_limit_buckets_expires_at",
        table_name="rate_limit_buckets",
    )
    op.drop_table("rate_limit_buckets")
