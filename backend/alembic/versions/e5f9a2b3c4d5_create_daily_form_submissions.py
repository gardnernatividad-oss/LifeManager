"""create daily form submissions

Revision ID: e5f9a2b3c4d5
Revises: d4e8f1a2b3c4
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f9a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d4e8f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

answer_type_enum = postgresql.ENUM("boolean", "text", "number", name="dailyformanswertype", create_type=False)


def upgrade() -> None:
    op.create_table(
        "daily_form_submissions",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_daily_form_submissions_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_daily_form_submissions_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["definition_id"], ["daily_form_definitions.id"], name="fk_daily_form_submissions_definition_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_daily_form_submissions"),
        sa.UniqueConstraint("workspace_id", "user_id", "submission_date", name="uq_daily_form_submissions_workspace_user_date"),
    )
    op.create_table(
        "daily_form_answers",
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_title", sa.String(length=255), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False),
        sa.Column("answer_type", answer_type_enum, nullable=False),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("number_value", sa.Float(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(answer_type = 'boolean' AND boolean_value IS NOT NULL AND text_value IS NULL AND number_value IS NULL) OR "
            "(answer_type = 'text' AND boolean_value IS NULL AND text_value IS NOT NULL AND number_value IS NULL) OR "
            "(answer_type = 'number' AND boolean_value IS NULL AND text_value IS NULL AND number_value IS NOT NULL)",
            name="ck_daily_form_answers_value_matches_type",
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["daily_form_submissions.id"], name="fk_daily_form_answers_submission_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_daily_form_answers"),
        sa.UniqueConstraint("submission_id", "question_id", name="uq_daily_form_answers_submission_question"),
    )


def downgrade() -> None:
    op.drop_table("daily_form_answers")
    op.drop_table("daily_form_submissions")
