"""Add safe delivery claims to notification jobs.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_notification_jobs_status_valid", "notification_jobs", type_="check")
    op.create_check_constraint(
        "ck_notification_jobs_status_valid",
        "notification_jobs",
        "status IN ('PENDING','PROCESSING','SENT','FAILED','CANCELLED')",
    )
    op.add_column("notification_jobs", sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_notification_jobs_notification",
        "notification_jobs",
        "notifications",
        ["notification_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_notification_jobs_notification_id", "notification_jobs", ["notification_id"])


def downgrade() -> None:
    op.drop_constraint("uq_notification_jobs_notification_id", "notification_jobs", type_="unique")
    op.drop_constraint("fk_notification_jobs_notification", "notification_jobs", type_="foreignkey")
    op.drop_column("notification_jobs", "notification_id")
    op.execute("UPDATE notification_jobs SET status = 'FAILED' WHERE status = 'PROCESSING'")
    op.drop_constraint("ck_notification_jobs_status_valid", "notification_jobs", type_="check")
    op.create_check_constraint(
        "ck_notification_jobs_status_valid",
        "notification_jobs",
        "status IN ('PENDING','SENT','FAILED','CANCELLED')",
    )
