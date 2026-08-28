"""Use decimal Project Stage progress and normalized one-based ordering.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_project_stages_position_nonnegative", "project_stages", type_="check")
    op.execute(
        """
        WITH ordered AS (
            SELECT id, row_number() OVER (PARTITION BY project_id ORDER BY position, id) AS new_position
            FROM project_stages
        )
        UPDATE project_stages AS stages
        SET position = -ordered.new_position
        FROM ordered
        WHERE stages.id = ordered.id
        """
    )
    op.execute("UPDATE project_stages SET position = -position")
    op.create_check_constraint("ck_project_stages_position_positive", "project_stages", "position >= 1")
    op.alter_column(
        "project_stages", "progress", existing_type=sa.SmallInteger(),
        type_=sa.Numeric(5, 2), existing_nullable=False,
        existing_server_default=sa.text("0"), server_default=sa.text("0.00"),
        postgresql_using="progress::numeric(5,2)",
    )
    op.alter_column(
        "project_stage_history", "progress", existing_type=sa.SmallInteger(),
        type_=sa.Numeric(5, 2), existing_nullable=False,
        postgresql_using="progress::numeric(5,2)",
    )
    op.add_column(
        "project_stage_history",
        sa.Column("previous_progress", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_stage_history", "previous_progress")
    op.alter_column(
        "project_stage_history", "progress", existing_type=sa.Numeric(5, 2),
        type_=sa.SmallInteger(), existing_nullable=False,
        postgresql_using="round(progress)::smallint",
    )
    op.alter_column(
        "project_stages", "progress", existing_type=sa.Numeric(5, 2),
        type_=sa.SmallInteger(), existing_nullable=False,
        existing_server_default=sa.text("0.00"), server_default=sa.text("0"),
        postgresql_using="round(progress)::smallint",
    )
    op.drop_constraint("ck_project_stages_position_positive", "project_stages", type_="check")
    op.create_check_constraint("ck_project_stages_position_nonnegative", "project_stages", "position >= 0")
