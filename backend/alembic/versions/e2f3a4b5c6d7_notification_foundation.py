"""Extend notification preferences and add logical jobs.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_reminder_preferences_type_valid", "reminder_preferences", type_="check")
    op.drop_constraint("ck_reminder_preferences_type_schedule", "reminder_preferences", type_="check")
    op.drop_constraint("ck_reminder_preferences_recurrence_shape", "reminder_preferences", type_="check")
    op.alter_column("reminder_preferences", "schedule_kind", existing_type=sa.String(16), nullable=True)
    op.alter_column("reminder_preferences", "local_time", existing_type=sa.Time(), nullable=True)
    op.create_check_constraint("ck_reminder_preferences_type_valid", "reminder_preferences", "reminder_type IN ('DAILY_SUMMARY','DAILY_REVIEW','PENDING_FOLLOW_UP','PROJECT_FOLLOW_UP','ACTIVITY_REMINDERS')")
    op.create_check_constraint("ck_reminder_preferences_type_schedule", "reminder_preferences", "(reminder_type IN ('DAILY_SUMMARY','DAILY_REVIEW') AND schedule_kind = 'DAILY') OR (reminder_type IN ('PENDING_FOLLOW_UP','PROJECT_FOLLOW_UP') AND schedule_kind = 'WEEKLY') OR (reminder_type = 'ACTIVITY_REMINDERS' AND schedule_kind IS NULL)")
    op.create_check_constraint("ck_reminder_preferences_recurrence_shape", "reminder_preferences", "(schedule_kind = 'DAILY' AND local_time IS NOT NULL AND weekdays IS NULL AND month_days IS NULL) OR (schedule_kind = 'WEEKLY' AND local_time IS NOT NULL AND weekdays IS NOT NULL AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (reminder_type = 'ACTIVITY_REMINDERS' AND local_time IS NULL AND weekdays IS NULL AND month_days IS NULL)")
    op.create_table(
        "notification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(48), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("notification_type IN ('WORKSPACE_INVITATION','INVITATION_ACCEPTED','INVITATION_REJECTED','MEMBER_REMOVED','OWNERSHIP_TRANSFERRED','TASK_ASSIGNED','TASK_REASSIGNED','PENDING_ASSIGNED','PENDING_REASSIGNED','PROJECT_LEADER_ASSIGNED','PROJECT_LEADER_REASSIGNED','PROJECT_STAGE_ASSIGNED','PROJECT_STAGE_REASSIGNED','ACTIVITY_CREATED','ACTIVITY_UPDATED','ACTIVITY_CANCELLED','ACTIVITY_PARTICIPANT_REMOVED','DAILY_SUMMARY_REMINDER','DAILY_REVIEW_REMINDER','PENDING_FOLLOW_UP_REMINDER','PROJECT_FOLLOW_UP_REMINDER','ACTIVITY_REMINDER')", name="ck_notification_jobs_type_valid"),
        sa.CheckConstraint("status IN ('PENDING','SENT','FAILED','CANCELLED')", name="ck_notification_jobs_status_valid"),
        sa.CheckConstraint("length(btrim(dedup_key)) > 0", name="ck_notification_jobs_dedup_not_blank"),
        sa.CheckConstraint("(status = 'SENT' AND sent_at IS NOT NULL) OR (status <> 'SENT' AND sent_at IS NULL)", name="ck_notification_jobs_sent_consistent"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notification_jobs_user", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_notification_jobs_dedup_key"),
    )
    op.create_index("ix_notification_jobs_pending_schedule", "notification_jobs", ["status", "scheduled_for", "id"])
    op.create_index("ix_notification_jobs_user_schedule", "notification_jobs", ["user_id", "scheduled_for", "id"])


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_user_schedule", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_pending_schedule", table_name="notification_jobs")
    op.drop_table("notification_jobs")
    op.drop_constraint("ck_reminder_preferences_recurrence_shape", "reminder_preferences", type_="check")
    op.drop_constraint("ck_reminder_preferences_type_schedule", "reminder_preferences", type_="check")
    op.drop_constraint("ck_reminder_preferences_type_valid", "reminder_preferences", type_="check")
    op.execute("DELETE FROM reminder_preferences WHERE reminder_type = 'ACTIVITY_REMINDERS'")
    op.alter_column("reminder_preferences", "local_time", existing_type=sa.Time(), nullable=False)
    op.alter_column("reminder_preferences", "schedule_kind", existing_type=sa.String(16), nullable=False)
    op.create_check_constraint("ck_reminder_preferences_type_valid", "reminder_preferences", "reminder_type IN ('DAILY_SUMMARY','DAILY_REVIEW','PENDING_FOLLOW_UP','PROJECT_FOLLOW_UP')")
    op.create_check_constraint("ck_reminder_preferences_type_schedule", "reminder_preferences", "((reminder_type IN ('DAILY_SUMMARY','DAILY_REVIEW') AND schedule_kind = 'DAILY') OR reminder_type IN ('PENDING_FOLLOW_UP','PROJECT_FOLLOW_UP'))")
    op.create_check_constraint("ck_reminder_preferences_recurrence_shape", "reminder_preferences", "(schedule_kind = 'DAILY' AND weekdays IS NULL AND month_days IS NULL) OR (schedule_kind = 'WEEKLY' AND weekdays IS NOT NULL AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (schedule_kind = 'MONTHLY' AND month_days IS NOT NULL AND lifemanager_smallint_array_unique_in_range(month_days, 1, 31) AND weekdays IS NULL)")
