"""Guarded destructive reset from the disposable V1 schema to V2.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

import os
from urllib.parse import unquote

from alembic import op
import sqlalchemy as sa


# Frozen V2 schema snapshot. Runtime application models are never imported here.
from enum import Enum


class StringEnum(str, Enum):
    pass


class AccountStatus(StringEnum):
    PENDING_EMAIL_VERIFICATION = "PENDING_EMAIL_VERIFICATION"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class GlobalRole(StringEnum):
    GLOBAL_ADMIN = "GLOBAL_ADMIN"


class WorkspaceKind(StringEnum):
    PERSONAL = "PERSONAL"
    SHARED = "SHARED"


class MembershipStatus(StringEnum):
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class CalendarVisibility(StringEnum):
    SHOW_DETAILS = "SHOW_DETAILS"
    AVAILABILITY_ONLY = "AVAILABILITY_ONLY"
    HIDE = "HIDE"


class InvitationStatus(StringEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AccountActionTokenType(StringEnum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"


class GenerationEntityType(StringEnum):
    TASK = "TASK"
    ACTIVITY = "ACTIVITY"


class GenerationPattern(StringEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class TaskResult(StringEnum):
    COMPLETED = "COMPLETED"
    NOT_COMPLETED = "NOT_COMPLETED"


class HistoryEventType(StringEnum):
    TRACKING = "TRACKING"
    CORRECTION = "CORRECTION"


class ActivityStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"


class ParticipantCalendarStatus(StringEnum):
    VISIBLE = "VISIBLE"
    REMOVED = "REMOVED"


class ReminderType(StringEnum):
    DAILY_SUMMARY = "DAILY_SUMMARY"
    DAILY_REVIEW = "DAILY_REVIEW"
    PENDING_FOLLOW_UP = "PENDING_FOLLOW_UP"
    PROJECT_FOLLOW_UP = "PROJECT_FOLLOW_UP"


class ScheduleKind(StringEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class NotificationType(StringEnum):
    WORKSPACE_INVITATION = "WORKSPACE_INVITATION"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED"
    INVITATION_REJECTED = "INVITATION_REJECTED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    OWNERSHIP_TRANSFERRED = "OWNERSHIP_TRANSFERRED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    PENDING_ASSIGNED = "PENDING_ASSIGNED"
    PENDING_REASSIGNED = "PENDING_REASSIGNED"
    PROJECT_LEADER_ASSIGNED = "PROJECT_LEADER_ASSIGNED"
    PROJECT_LEADER_REASSIGNED = "PROJECT_LEADER_REASSIGNED"
    PROJECT_STAGE_ASSIGNED = "PROJECT_STAGE_ASSIGNED"
    PROJECT_STAGE_REASSIGNED = "PROJECT_STAGE_REASSIGNED"
    ACTIVITY_CREATED = "ACTIVITY_CREATED"
    ACTIVITY_UPDATED = "ACTIVITY_UPDATED"
    ACTIVITY_CANCELLED = "ACTIVITY_CANCELLED"
    ACTIVITY_PARTICIPANT_REMOVED = "ACTIVITY_PARTICIPANT_REMOVED"
    DAILY_SUMMARY_REMINDER = "DAILY_SUMMARY_REMINDER"
    DAILY_REVIEW_REMINDER = "DAILY_REVIEW_REMINDER"
    PENDING_FOLLOW_UP_REMINDER = "PENDING_FOLLOW_UP_REMINDER"
    PROJECT_FOLLOW_UP_REMINDER = "PROJECT_FOLLOW_UP_REMINDER"
    ACTIVITY_REMINDER = "ACTIVITY_REMINDER"


class DeliveryStatus(StringEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time,
    UniqueConstraint, desc, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class FrozenBase(DeclarativeBase):
    pass


class FrozenBaseEntity(FrozenBase):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False)


Base = FrozenBase
BaseEntity = FrozenBaseEntity


def _values(enum: type) -> str:
    return ", ".join(f"'{item.value}'" for item in enum)


def _enum_check(column: str, enum: type, name: str, nullable: bool = False) -> CheckConstraint:
    prefix = f"{column} IS NULL OR " if nullable else ""
    return CheckConstraint(f"{prefix}{column} IN ({_values(enum)})", name=name)


class User(BaseEntity):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("length(btrim(email)) > 0", name="ck_users_email_not_blank"),
        CheckConstraint("length(btrim(first_name)) > 0", name="ck_users_first_name_not_blank"),
        CheckConstraint("length(btrim(last_name)) > 0", name="ck_users_last_name_not_blank"),
        CheckConstraint("length(btrim(timezone)) > 0", name="ck_users_timezone_not_blank"),
        _enum_check("account_status", AccountStatus, "ck_users_account_status_valid"),
        _enum_check("global_role", GlobalRole, "ck_users_global_role_valid", True),
        CheckConstraint(
            "(account_status = 'PENDING_EMAIL_VERIFICATION' AND email_verified_at IS NULL) OR "
            "(account_status <> 'PENDING_EMAIL_VERIFICATION' AND email_verified_at IS NOT NULL)",
            name="ck_users_verification_consistent",
        ),
        CheckConstraint("lock_version > 0", name="ck_users_lock_version_positive"),
        Index("ix_users_email", "email"),
        Index("uq_users_global_admin", "global_role", unique=True,
              postgresql_where=text("global_role = 'GLOBAL_ADMIN'")),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), default="America/Lima", server_default=text("'America/Lima'"), nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(String(32), default=AccountStatus.PENDING_EMAIL_VERIFICATION, server_default=text("'PENDING_EMAIL_VERIFICATION'"), nullable=False)
    global_role: Mapped[GlobalRole | None] = mapped_column(String(32), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class UserAccountStateEvent(Base):
    __tablename__ = "user_account_state_events"
    __table_args__ = (
        _enum_check("from_status", AccountStatus, "ck_user_state_events_from_status_valid", True),
        _enum_check("to_status", AccountStatus, "ck_user_state_events_to_status_valid"),
        Index("ix_user_state_events_user_created", "user_id", desc("created_at"), "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[AccountStatus | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[AccountStatus] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class AccountActionToken(Base):
    __tablename__ = "account_action_tokens"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_account_action_tokens_digest"),
        _enum_check("token_type", AccountActionTokenType, "ck_account_tokens_type_valid"),
        CheckConstraint("expires_at > created_at", name="ck_account_tokens_expiry"),
        CheckConstraint("NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)", name="ck_account_tokens_terminal_exclusive"),
        Index("ix_account_tokens_user_type_expires", "user_id", "token_type", "expires_at"),
        Index("uq_account_tokens_active_user_type", "user_id", "token_type", unique=True,
              postgresql_where=text("consumed_at IS NULL AND revoked_at IS NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_type: Mapped[AccountActionTokenType] = mapped_column(String(32), nullable=False)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Workspace(BaseEntity):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_workspaces_name_not_blank"),
        _enum_check("kind", WorkspaceKind, "ck_workspaces_kind_valid"),
        CheckConstraint("lock_version > 0", name="ck_workspaces_lock_version_positive"),
        Index("uq_workspaces_personal_owner", "owner_user_id", unique=True, postgresql_where=text("kind = 'PERSONAL'")),
        Index("ix_workspaces_owner_kind_id", "owner_user_id", "kind", "id"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[WorkspaceKind] = mapped_column(String(20), default=WorkspaceKind.PERSONAL, server_default=text("'PERSONAL'"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class WorkspaceMember(BaseEntity):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
        UniqueConstraint("id", "workspace_id", name="uq_workspace_members_id_workspace"),
        _enum_check("status", MembershipStatus, "ck_workspace_members_status_valid"),
        _enum_check("calendar_visibility", CalendarVisibility, "ck_workspace_members_visibility_valid"),
        CheckConstraint("(status = 'ACTIVE' AND ended_at IS NULL) OR (status IN ('LEFT','REMOVED') AND ended_at IS NOT NULL)", name="ck_workspace_members_lifecycle_consistent"),
        CheckConstraint("lock_version > 0", name="ck_workspace_members_lock_version_positive"),
        Index("ix_workspace_members_user_status_workspace", "user_id", "status", "workspace_id"),
        Index("ix_workspace_members_workspace_status_user", "workspace_id", "status", "user_id"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(String(16), default=MembershipStatus.ACTIVE, server_default=text("'ACTIVE'"), nullable=False)
    calendar_visibility: Mapped[CalendarVisibility] = mapped_column(String(24), default=CalendarVisibility.HIDE, server_default=text("'HIDE'"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


MEMBERSHIP_FK = ["workspace_members.workspace_id", "workspace_members.user_id"]


class WorkspaceInvitation(Base):
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "inviter_user_id"], MEMBERSHIP_FK, name="fk_workspace_invitations_inviter_membership", ondelete="RESTRICT"),
        UniqueConstraint("token_digest", name="uq_workspace_invitations_token_digest"),
        _enum_check("status", InvitationStatus, "ck_workspace_invitations_status_valid"),
        CheckConstraint("expires_at > created_at", name="ck_workspace_invitations_expiry"),
        CheckConstraint("(status = 'PENDING' AND responded_at IS NULL AND cancelled_at IS NULL) OR (status IN ('ACCEPTED','REJECTED','EXPIRED') AND responded_at IS NOT NULL AND cancelled_at IS NULL) OR (status = 'CANCELLED' AND cancelled_at IS NOT NULL)", name="ck_workspace_invitations_response_consistent"),
        Index("uq_workspace_invitations_pending_email", "workspace_id", "recipient_email", unique=True, postgresql_where=text("status = 'PENDING'")),
        Index("ix_workspace_invitations_recipient_status_created", "recipient_user_id", "status", desc("created_at")),
        Index("ix_workspace_invitations_expires", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    inviter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(String(16), default=InvitationStatus.PENDING, server_default=text("'PENDING'"), nullable=False)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class CatalogMixin:
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str]
    normalized_name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class Category(CatalogMixin, BaseEntity):
    __tablename__ = "categories"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_categories_workspace_id", ondelete="CASCADE"),
        UniqueConstraint("workspace_id", "normalized_name", name="uq_categories_workspace_normalized_name"),
        UniqueConstraint("id", "workspace_id", name="uq_categories_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_categories_name_not_blank"),
        CheckConstraint("lock_version > 0", name="ck_categories_lock_version_positive"),
        Index("ix_categories_workspace_active_name_id", "workspace_id", "is_active", "normalized_name", "id"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)


class MasterTask(CatalogMixin, BaseEntity):
    __tablename__ = "master_tasks"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_master_tasks_workspace_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_master_tasks_category_workspace", ondelete="RESTRICT"),
        UniqueConstraint("workspace_id", "normalized_name", name="uq_master_tasks_workspace_normalized_name"),
        UniqueConstraint("id", "workspace_id", name="uq_master_tasks_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_master_tasks_name_not_blank"),
        CheckConstraint("lock_version > 0", name="ck_master_tasks_lock_version_positive"),
        Index("ix_master_tasks_workspace_active_category_name_id", "workspace_id", "is_active", "category_id", "normalized_name", "id"),
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)


class ActivityMaster(CatalogMixin, BaseEntity):
    __tablename__ = "activity_masters"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_activity_masters_workspace_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_activity_masters_category_workspace", ondelete="RESTRICT"),
        UniqueConstraint("workspace_id", "normalized_name", name="uq_activity_masters_workspace_normalized_name"),
        UniqueConstraint("id", "workspace_id", name="uq_activity_masters_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_activity_masters_name_not_blank"),
        CheckConstraint("lock_version > 0", name="ck_activity_masters_lock_version_positive"),
        Index("ix_activity_masters_workspace_active_category_name_id", "workspace_id", "is_active", "category_id", "normalized_name", "id"),
    )
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)


class GenerationBatch(Base):
    __tablename__ = "generation_batches"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "created_by_user_id"], MEMBERSHIP_FK, name="fk_generation_batches_creator_membership", ondelete="RESTRICT"),
        UniqueConstraint("id", "workspace_id", name="uq_generation_batches_id_workspace"),
        _enum_check("entity_type", GenerationEntityType, "ck_generation_batches_entity_type_valid"),
        _enum_check("pattern", GenerationPattern, "ck_generation_batches_pattern_valid"),
        CheckConstraint("date_until >= date_from", name="ck_generation_batches_date_range"),
        CheckConstraint("(pattern = 'DAILY' AND weekdays IS NULL AND month_days IS NULL) OR (pattern = 'WEEKLY' AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (pattern = 'MONTHLY' AND lifemanager_smallint_array_unique_in_range(month_days, 1, 31) AND weekdays IS NULL)", name="ck_generation_batches_recurrence_shape"),
        CheckConstraint("(entity_type = 'TASK' AND timezone IS NULL) OR (entity_type = 'ACTIVITY' AND timezone IS NOT NULL AND length(btrim(timezone)) > 0)", name="ck_generation_batches_timezone_shape"),
        Index("ix_generation_batches_workspace_type_created", "workspace_id", "entity_type", desc("created_at")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[GenerationEntityType] = mapped_column(String(16), nullable=False)
    pattern: Mapped[GenerationPattern] = mapped_column(String(16), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_until: Mapped[date] = mapped_column(Date, nullable=False)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    month_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Task(BaseEntity):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(["master_task_id", "workspace_id"], ["master_tasks.id", "master_tasks.workspace_id"], name="fk_tasks_master_task_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "responsible_user_id"], MEMBERSHIP_FK, name="fk_tasks_responsible_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "created_by_user_id"], MEMBERSHIP_FK, name="fk_tasks_creator_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "resolved_by_user_id"], MEMBERSHIP_FK, name="fk_tasks_resolver_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["generation_batch_id", "workspace_id"], ["generation_batches.id", "generation_batches.workspace_id"], name="fk_tasks_batch_workspace", ondelete="RESTRICT"),
        UniqueConstraint("workspace_id", "master_task_id", "planned_date", "responsible_user_id", name="uq_tasks_workspace_master_date_responsible"),
        _enum_check("result", TaskResult, "ck_tasks_result_valid", True),
        CheckConstraint("(result IS NULL AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR (result IS NOT NULL AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)", name="ck_tasks_resolution_consistent"),
        CheckConstraint("lock_version > 0", name="ck_tasks_lock_version_positive"),
        Index("ix_tasks_responsible_result_date_workspace_id", "responsible_user_id", "result", "planned_date", "workspace_id", "id"),
        Index("ix_tasks_workspace_date_id", "workspace_id", desc("planned_date"), "id"),
        Index("ix_tasks_workspace_master_date", "workspace_id", "master_task_id", desc("planned_date")),
        Index("ix_tasks_batch_date_id", "generation_batch_id", "planned_date", "id", postgresql_where=text("generation_batch_id IS NOT NULL")),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    master_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[TaskResult | None] = mapped_column(String(20), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    generation_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class PendingItem(BaseEntity):
    __tablename__ = "pending_items"
    __table_args__ = (
        ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_pending_items_category_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "responsible_user_id"], MEMBERSHIP_FK, name="fk_pending_items_responsible_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "created_by_user_id"], MEMBERSHIP_FK, name="fk_pending_items_creator_membership", ondelete="RESTRICT"),
        UniqueConstraint("id", "workspace_id", name="uq_pending_items_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_pending_items_name_not_blank"),
        CheckConstraint("(is_active AND planned_date IS NOT NULL) OR (NOT is_active AND planned_date IS NULL)", name="ck_pending_items_planned_date_lifecycle"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_pending_items_progress_range"),
        CheckConstraint("(progress = 100 AND completion_date IS NOT NULL) OR (progress < 100 AND completion_date IS NULL)", name="ck_pending_items_completion_consistent"),
        CheckConstraint("lock_version > 0", name="ck_pending_items_lock_version_positive"),
        Index("ix_pending_responsible_active_progress_date", "responsible_user_id", "is_active", "progress", "planned_date", "workspace_id", "id"),
        Index("ix_pending_workspace_active_date_id", "workspace_id", "is_active", "planned_date", "id"),
        Index("ix_pending_workspace_category_date", "workspace_id", "category_id", "planned_date"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class PendingItemHistory(Base):
    __tablename__ = "pending_item_history"
    __table_args__ = (
        ForeignKeyConstraint(["pending_item_id", "workspace_id"], ["pending_items.id", "pending_items.workspace_id"], name="fk_pending_item_history_item_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "actor_user_id"], MEMBERSHIP_FK, name="fk_pending_item_history_actor_membership", ondelete="RESTRICT"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_pending_item_history_progress_range"),
        _enum_check("event_type", HistoryEventType, "ck_pending_item_history_event_type_valid"),
        CheckConstraint("comment IS NULL OR length(btrim(comment)) > 0", name="ck_pending_item_history_comment_not_blank"),
        Index("ix_pending_history_item_recorded_id", "pending_item_id", desc("recorded_at"), "id"),
        Index("ix_pending_history_workspace_recorded", "workspace_id", desc("recorded_at")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pending_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[HistoryEventType] = mapped_column(String(16), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Project(BaseEntity):
    __tablename__ = "projects"
    __table_args__ = (
        ForeignKeyConstraint(["category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_projects_category_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "leader_user_id"], MEMBERSHIP_FK, name="fk_projects_leader_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "created_by_user_id"], MEMBERSHIP_FK, name="fk_projects_creator_membership", ondelete="RESTRICT"),
        UniqueConstraint("id", "workspace_id", name="uq_projects_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name_not_blank"),
        CheckConstraint("lock_version > 0", name="ck_projects_lock_version_positive"),
        Index("ix_projects_workspace_active_category_name_id", "workspace_id", "is_active", "category_id", "name", "id"),
        Index("ix_projects_leader_active_workspace_id", "leader_user_id", "is_active", "workspace_id", "id"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leader_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class ProjectLeaderHistory(Base):
    __tablename__ = "project_leader_history"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "workspace_id"], ["projects.id", "projects.workspace_id"], name="fk_project_leader_history_project_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "leader_user_id"], MEMBERSHIP_FK, name="fk_project_leader_history_leader_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "actor_user_id"], MEMBERSHIP_FK, name="fk_project_leader_history_actor_membership", ondelete="RESTRICT"),
        Index("ix_project_leader_history_project_recorded", "project_id", desc("recorded_at"), "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leader_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class ProjectStage(BaseEntity):
    __tablename__ = "project_stages"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "workspace_id"], ["projects.id", "projects.workspace_id"], name="fk_project_stages_project_workspace", ondelete="CASCADE"),
        ForeignKeyConstraint(["workspace_id", "responsible_user_id"], MEMBERSHIP_FK, name="fk_project_stages_responsible_membership", ondelete="RESTRICT"),
        UniqueConstraint("project_id", "position", name="uq_project_stages_project_position"),
        UniqueConstraint("id", "workspace_id", name="uq_project_stages_id_workspace"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_project_stages_name_not_blank"),
        CheckConstraint("position >= 0", name="ck_project_stages_position_nonnegative"),
        CheckConstraint("weight > 0 AND weight <= 100", name="ck_project_stages_weight_range"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_project_stages_progress_range"),
        CheckConstraint("(progress = 100 AND completion_date IS NOT NULL) OR (progress < 100 AND completion_date IS NULL)", name="ck_project_stages_completion_consistent"),
        CheckConstraint("lock_version > 0", name="ck_project_stages_lock_version_positive"),
        Index("ix_project_stages_project_position_id", "project_id", "position", "id"),
        Index("ix_project_stages_responsible_progress_date", "responsible_user_id", "progress", "planned_date", "workspace_id", "id"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class ProjectStageHistory(Base):
    __tablename__ = "project_stage_history"
    __table_args__ = (
        ForeignKeyConstraint(["project_stage_id", "workspace_id"], ["project_stages.id", "project_stages.workspace_id"], name="fk_project_stage_history_stage_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "actor_user_id"], MEMBERSHIP_FK, name="fk_project_stage_history_actor_membership", ondelete="RESTRICT"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_project_stage_history_progress_range"),
        _enum_check("event_type", HistoryEventType, "ck_project_stage_history_event_type_valid"),
        CheckConstraint("comment IS NULL OR length(btrim(comment)) > 0", name="ck_project_stage_history_comment_not_blank"),
        Index("ix_project_stage_history_stage_recorded", "project_stage_id", desc("recorded_at"), "id"),
        Index("ix_project_stage_history_workspace_recorded", "workspace_id", desc("recorded_at")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[HistoryEventType] = mapped_column(String(16), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Activity(BaseEntity):
    __tablename__ = "activities"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "organizer_user_id"], MEMBERSHIP_FK, name="fk_activities_organizer_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["activity_master_id", "workspace_id"], ["activity_masters.id", "activity_masters.workspace_id"], name="fk_activities_master_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["custom_category_id", "workspace_id"], ["categories.id", "categories.workspace_id"], name="fk_activities_custom_category_workspace", ondelete="RESTRICT"),
        ForeignKeyConstraint(["workspace_id", "cancelled_by_user_id"], MEMBERSHIP_FK, name="fk_activities_canceller_membership", ondelete="RESTRICT"),
        ForeignKeyConstraint(["generation_batch_id", "workspace_id"], ["generation_batches.id", "generation_batches.workspace_id"], name="fk_activities_batch_workspace", ondelete="RESTRICT"),
        UniqueConstraint("id", "workspace_id", name="uq_activities_id_workspace"),
        CheckConstraint("(activity_master_id IS NOT NULL AND custom_category_id IS NULL) OR (activity_master_id IS NULL AND custom_category_id IS NOT NULL)", name="ck_activities_source_xor"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_activities_title_not_blank"),
        CheckConstraint("ends_at > starts_at", name="ck_activities_time_range"),
        _enum_check("status", ActivityStatus, "ck_activities_status_valid"),
        CheckConstraint("(status = 'SCHEDULED' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL) OR (status = 'CANCELLED' AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL)", name="ck_activities_cancellation_consistent"),
        CheckConstraint("lock_version > 0", name="ck_activities_lock_version_positive"),
        Index("ix_activities_workspace_starts_ends", "workspace_id", "starts_at", "ends_at"),
        Index("ix_activities_organizer_starts_id", "organizer_user_id", "starts_at", "id"),
        Index("ix_activities_batch_starts_id", "generation_batch_id", "starts_at", "id"),
        Index("uq_activities_batch_starts", "generation_batch_id", "starts_at", unique=True, postgresql_where=text("generation_batch_id IS NOT NULL")),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    activity_master_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    custom_category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ActivityStatus] = mapped_column(String(16), default=ActivityStatus.SCHEDULED, server_default=text("'SCHEDULED'"), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    generation_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class ActivityParticipant(BaseEntity):
    __tablename__ = "activity_participants"
    __table_args__ = (
        ForeignKeyConstraint(["activity_id", "workspace_id"], ["activities.id", "activities.workspace_id"], name="fk_activity_participants_activity_workspace", ondelete="CASCADE"),
        ForeignKeyConstraint(["workspace_id", "user_id"], MEMBERSHIP_FK, name="fk_activity_participants_user_membership", ondelete="RESTRICT"),
        UniqueConstraint("activity_id", "user_id", name="uq_activity_participants_activity_user"),
        _enum_check("calendar_status", ParticipantCalendarStatus, "ck_activity_participants_status_valid"),
        CheckConstraint("(calendar_status = 'VISIBLE' AND removed_at IS NULL) OR (calendar_status = 'REMOVED' AND removed_at IS NOT NULL)", name="ck_activity_participants_lifecycle_consistent"),
        CheckConstraint("lock_version > 0", name="ck_activity_participants_lock_version_positive"),
        Index("ix_activity_participants_user_status_activity", "user_id", "calendar_status", "activity_id"),
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calendar_status: Mapped[ParticipantCalendarStatus] = mapped_column(String(16), default=ParticipantCalendarStatus.VISIBLE, server_default=text("'VISIBLE'"), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class ActivityReminder(BaseEntity):
    __tablename__ = "activity_reminders"
    __table_args__ = (
        ForeignKeyConstraint(["activity_id", "workspace_id"], ["activities.id", "activities.workspace_id"], name="fk_activity_reminders_activity_workspace", ondelete="CASCADE"),
        ForeignKeyConstraint(["workspace_id", "user_id"], MEMBERSHIP_FK, name="fk_activity_reminders_user_membership", ondelete="RESTRICT"),
        UniqueConstraint("activity_id", "user_id", name="uq_activity_reminders_activity_user"),
        CheckConstraint("minutes_before >= 0", name="ck_activity_reminders_minutes_nonnegative"),
        CheckConstraint("lock_version > 0", name="ck_activity_reminders_lock_version_positive"),
        Index("ix_activity_reminders_schedule", "is_enabled", "last_scheduled_for", "activity_id"),
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    minutes_before: Mapped[int] = mapped_column(Integer, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    last_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class UserReviewMetadata(Base):
    __tablename__ = "user_review_metadata"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tasks_last_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_items_last_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project_stages_last_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False)


class ReminderPreference(BaseEntity):
    __tablename__ = "reminder_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "reminder_type", name="uq_reminder_preferences_user_type"),
        _enum_check("reminder_type", ReminderType, "ck_reminder_preferences_type_valid"),
        _enum_check("schedule_kind", ScheduleKind, "ck_reminder_preferences_schedule_valid"),
        CheckConstraint("((reminder_type IN ('DAILY_SUMMARY','DAILY_REVIEW') AND schedule_kind = 'DAILY') OR reminder_type IN ('PENDING_FOLLOW_UP','PROJECT_FOLLOW_UP'))", name="ck_reminder_preferences_type_schedule"),
        CheckConstraint("(schedule_kind = 'DAILY' AND weekdays IS NULL AND month_days IS NULL) OR (schedule_kind = 'WEEKLY' AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (schedule_kind = 'MONTHLY' AND lifemanager_smallint_array_unique_in_range(month_days, 1, 31) AND weekdays IS NULL)", name="ck_reminder_preferences_recurrence_shape"),
        CheckConstraint("lock_version > 0", name="ck_reminder_preferences_lock_version_positive"),
        Index("ix_reminder_preferences_enabled_type_time", "is_enabled", "reminder_type", "local_time"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reminder_type: Mapped[ReminderType] = mapped_column(String(32), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    schedule_kind: Mapped[ScheduleKind] = mapped_column(String(16), nullable=False)
    local_time: Mapped[time] = mapped_column(Time, nullable=False)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    month_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        _enum_check("notification_type", NotificationType, "ck_notifications_type_valid"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_notifications_title_not_blank"),
        CheckConstraint("length(btrim(body)) > 0", name="ck_notifications_body_not_blank"),
        CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="ck_notifications_expiry"),
        Index("uq_notifications_recipient_dedup", "recipient_user_id", "dedup_key", unique=True, postgresql_where=text("dedup_key IS NOT NULL")),
        Index("ix_notifications_unread_recipient_created", "recipient_user_id", desc("created_at"), "id", postgresql_where=text("read_at IS NULL")),
        Index("ix_notifications_recipient_created", "recipient_user_id", desc("created_at"), "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    notification_type: Mapped[NotificationType] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PushSubscription(BaseEntity):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint_hash", name="uq_push_subscriptions_endpoint_hash"),
        CheckConstraint("(is_active AND invalidated_at IS NULL) OR (NOT is_active AND invalidated_at IS NOT NULL)", name="ck_push_subscriptions_lifecycle_consistent"),
        Index("ix_push_subscriptions_user_active_id", "user_id", "is_active", "id"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    endpoint_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    endpoint_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    p256dh_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    auth_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "push_subscription_id", name="uq_notification_deliveries_notification_subscription"),
        _enum_check("status", DeliveryStatus, "ck_notification_deliveries_status_valid"),
        CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempts_nonnegative"),
        CheckConstraint("(status = 'DELIVERED' AND delivered_at IS NOT NULL) OR (status <> 'DELIVERED' AND delivered_at IS NULL)", name="ck_notification_deliveries_delivery_consistent"),
        Index("ix_notification_deliveries_pending", "status", "next_attempt_at", "id", postgresql_where=text("status = 'PENDING'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    push_subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("push_subscriptions.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(String(16), default=DeliveryStatus.PENDING, server_default=text("'PENDING'"), nullable=False)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False)

V2_METADATA = Base.metadata


revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

V1_TABLES = {
    "categories", "master_tasks", "pending_items", "project_steps", "projects",
    "tasks", "users", "workspace_members", "workspace_tracking_metadata", "workspaces",
}
V1_DROP_ORDER = (
    "project_steps", "projects", "pending_items", "tasks", "master_tasks",
    "categories", "workspace_tracking_metadata", "workspace_members", "workspaces", "users",
)
SENTINEL_COLUMNS = {
    "users": {"id", "email", "hashed_password"},
    "workspaces": {"id", "kind"},
    "workspace_members": {"id", "workspace_id", "user_id", "role"},
    "tasks": {"id", "workspace_id", "master_task_id", "planned_date"},
    "project_steps": {"id", "project_id", "name", "position"},
}


def _assert_safe_target(bind: sa.Connection) -> None:
    if os.getenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET") != "1":
        raise RuntimeError("V2 reset refused: LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET=1 is required")
    environment = os.getenv("LIFEMANAGER_ENV", "").strip().lower()
    if environment not in {"local", "development", "test", "testing"}:
        raise RuntimeError("V2 reset refused: LIFEMANAGER_ENV must identify local/development/test")
    url = bind.engine.url
    host = (url.host or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("V2 reset refused: database host is not loopback/local")
    if "neon" in host or "production" in host or "prod" in host:
        raise RuntimeError("V2 reset refused: production/Neon target denied")
    database = unquote(url.database or "")
    configured = {item.strip() for item in os.getenv("LIFEMANAGER_DESTRUCTIVE_DB_ALLOWLIST", "").split(",") if item.strip()}
    allowlist = {"lifemanager", "lifemanager_test", "lifemanager_v2_test"} | configured
    if database not in allowlist:
        raise RuntimeError("V2 reset refused: database name is not explicitly allowlisted")
    current_revision = bind.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    if current_revision != down_revision:
        raise RuntimeError(f"V2 reset refused: expected prior revision {down_revision}")
    inspector = sa.inspect(bind)
    public_tables = set(inspector.get_table_names(schema="public")) - {"alembic_version"}
    if public_tables != V1_TABLES:
        raise RuntimeError("V2 reset refused: public application-table set is not the expected V1 schema")
    for table, expected_columns in SENTINEL_COLUMNS.items():
        actual = {column["name"] for column in inspector.get_columns(table, schema="public")}
        if not expected_columns <= actual:
            raise RuntimeError(f"V2 reset refused: V1 sentinel columns differ for {table}")
    enum_types = set(bind.execute(sa.text("SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype='e'")).scalars())
    if enum_types != {"workspacerole"}:
        raise RuntimeError("V2 reset refused: PostgreSQL enum-type set is not the expected V1 shape")


def _create_support_functions() -> None:
    op.execute("""
    CREATE FUNCTION lifemanager_smallint_array_unique_in_range(values_ SMALLINT[], minimum_ INTEGER, maximum_ INTEGER)
    RETURNS BOOLEAN LANGUAGE SQL IMMUTABLE STRICT AS $$
      SELECT cardinality(values_) > 0 AND (SELECT count(*) = count(DISTINCT value_) AND bool_and(value_ BETWEEN minimum_ AND maximum_) FROM unnest(values_) AS value_)
    $$
    """)


def _create_integrity_triggers() -> None:
    op.execute("""
    CREATE FUNCTION lifemanager_assert_workspace_owner_active_member() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target_workspace UUID;
    BEGIN
      IF TG_TABLE_NAME = 'workspaces' THEN target_workspace := COALESCE(NEW.id, OLD.id);
      ELSE target_workspace := COALESCE(NEW.workspace_id, OLD.workspace_id); END IF;
      IF EXISTS (SELECT 1 FROM workspaces WHERE id=target_workspace) AND NOT EXISTS (
        SELECT 1 FROM workspaces w JOIN workspace_members m ON m.workspace_id=w.id AND m.user_id=w.owner_user_id AND m.status='ACTIVE' WHERE w.id=target_workspace
      ) THEN RAISE EXCEPTION 'workspace owner must have an ACTIVE membership' USING ERRCODE='23514'; END IF;
      RETURN COALESCE(NEW, OLD);
    END $$
    """)
    op.execute("CREATE CONSTRAINT TRIGGER ct_workspaces_owner_active_member AFTER INSERT OR UPDATE OF owner_user_id ON workspaces DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lifemanager_assert_workspace_owner_active_member()")
    op.execute("CREATE CONSTRAINT TRIGGER ct_workspace_members_owner_active_member AFTER INSERT OR UPDATE OR DELETE ON workspace_members DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lifemanager_assert_workspace_owner_active_member()")
    op.execute("""
    CREATE FUNCTION lifemanager_assert_occurrence_batch_entity_type() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actual_type VARCHAR(16);
    BEGIN
      IF NEW.generation_batch_id IS NULL THEN RETURN NEW; END IF;
      SELECT entity_type INTO actual_type FROM generation_batches WHERE id=NEW.generation_batch_id AND workspace_id=NEW.workspace_id;
      IF actual_type IS DISTINCT FROM TG_ARGV[0] THEN RAISE EXCEPTION 'generation batch entity type mismatch' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("CREATE CONSTRAINT TRIGGER ct_tasks_batch_entity_type AFTER INSERT OR UPDATE OF generation_batch_id, workspace_id ON tasks DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lifemanager_assert_occurrence_batch_entity_type('TASK')")
    op.execute("CREATE CONSTRAINT TRIGGER ct_activities_batch_entity_type AFTER INSERT OR UPDATE OF generation_batch_id, workspace_id ON activities DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lifemanager_assert_occurrence_batch_entity_type('ACTIVITY')")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_safe_target(bind)
    for table_name in V1_DROP_ORDER:
        op.drop_table(table_name)
    op.execute("DROP TYPE workspacerole")
    _create_support_functions()
    for table in V2_METADATA.sorted_tables:
        table.create(bind=bind, checkfirst=False)
    _create_integrity_triggers()


def downgrade() -> None:
    raise RuntimeError("V2 destructive reset is irreversible: discarded V1 data and schema cannot be reconstructed")
