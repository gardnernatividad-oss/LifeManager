"""create daily form definition

Revision ID: d4e8f1a2b3c4
Revises: a7d0e3f5c824
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e8f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "a7d0e3f5c824"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

answer_type_enum = postgresql.ENUM(
    "boolean",
    "text",
    "number",
    name="dailyformanswertype",
    create_type=False,
)


def upgrade() -> None:
    answer_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "daily_form_definitions",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_daily_form_definitions_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_form_definitions"),
        sa.UniqueConstraint("workspace_id", name="uq_daily_form_definitions_workspace_id"),
    )
    op.create_table(
        "daily_form_questions",
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("answer_type", answer_type_enum, nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint('"order" >= 1', name="ck_daily_form_questions_order_positive"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_daily_form_questions_title_not_blank"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["daily_form_definitions.id"],
            name="fk_daily_form_questions_definition_id_definitions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_form_questions"),
        sa.UniqueConstraint(
            "definition_id", "order",
            name="uq_daily_form_questions_definition_id_order",
        ),
    )


def downgrade() -> None:
    op.drop_table("daily_form_questions")
    op.drop_table("daily_form_definitions")
    answer_type_enum.drop(op.get_bind(), checkfirst=True)
