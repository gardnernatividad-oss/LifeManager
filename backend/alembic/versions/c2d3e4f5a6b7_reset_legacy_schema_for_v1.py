"""Reset disposable legacy schema and create V1 identity foundation.

Revision ID: c2d3e4f5a6b7
Revises: 1b2c3d4e5f60
Create Date: 2026-08-12
"""

from collections.abc import Sequence
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "1b2c3d4e5f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


workspace_role_enum = postgresql.ENUM(
    "OWNER", "ADMIN", "MEMBER", "VIEWER", name="workspacerole", create_type=False
)


def _require_explicit_development_database(bind: sa.Connection) -> None:
    if os.getenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET") != "1":
        raise RuntimeError(
            "Destructive V1 schema reset refused. Set "
            "LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET=1 only for the verified "
            "local LifeManager development/test database."
        )

    database_name, server_address = bind.execute(
        sa.text("SELECT current_database(), inet_server_addr()::text")
    ).one()
    is_lifemanager_database = database_name == "lifemanager" or database_name.startswith(
        "lifemanager_stage4_"
    )
    is_local_server = server_address in {"127.0.0.1/32", "::1/128"}
    if not is_lifemanager_database or not is_local_server:
        raise RuntimeError(
            "Destructive V1 schema reset refused for database "
            f"{database_name!r} at {server_address!r}."
        )


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    _require_explicit_development_database(op.get_bind())
    # All rows are approved disposable development data. Explicit application
    # table names prevent this revision from affecting unrelated schemas.
    for table_name in (
        "daily_form_answers",
        "daily_form_submissions",
        "daily_form_questions",
        "daily_form_definitions",
        "workspace_settings",
        "user_settings",
        "tasks",
        "task_series",
        "projects",
        "categories",
        "workspace_members",
        "workspaces",
        "users",
    ):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

    for type_name in (
        "dailyformanswertype",
        "weekstartson",
        "taskoutcome",
        "taskseriesfrequency",
        "workspacerole",
        "taskstatus",
        "taskpriority",
    ):
        op.execute(sa.text(f'DROP TYPE IF EXISTS "{type_name}"'))

    op.create_table(
        "users",
        *_audit_columns(),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=100), server_default=sa.text("'America/Lima'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("length(btrim(first_name)) > 0", name="ck_users_first_name_not_blank"),
        sa.CheckConstraint("length(btrim(last_name)) > 0", name="ck_users_last_name_not_blank"),
        sa.CheckConstraint("length(btrim(timezone)) > 0", name="ck_users_timezone_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "workspaces",
        *_audit_columns(),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default=sa.text("'PERSONAL'"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_workspaces_name_not_blank"),
        sa.CheckConstraint("kind IN ('PERSONAL', 'COLLABORATIVE')", name="ck_workspaces_kind_valid"),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )

    workspace_role_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "workspace_members",
        *_audit_columns(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", workspace_role_enum, nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_members_workspace_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_workspace_members_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_members"),
        sa.UniqueConstraint("user_id", "workspace_id", name="uq_workspace_members_user_id_workspace_id"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"], unique=False)
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"], unique=False)

    op.create_table(
        "workspace_tracking_metadata",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_review_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_items_last_tracking_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_tracking_metadata_workspace_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", name="pk_workspace_tracking_metadata"),
    )


def downgrade() -> None:
    raise RuntimeError(
        "The V1 schema reset discards approved disposable development data and "
        "cannot reconstruct the legacy head. Recreate a disposable database and "
        "upgrade to the desired revision instead."
    )
