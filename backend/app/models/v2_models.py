"""Authoritative SQLAlchemy graph for the LifeManager V2 physical schema."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, LargeBinary, Numeric, PrimaryKeyConstraint, SmallInteger,
    String, Text, Time, UniqueConstraint, desc, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseEntity
from app.models.enums import (
    AccountActionTokenType, AccountStatus, ActivityStatus, CalendarVisibility,
    DeliveryStatus, GenerationEntityType, GenerationPattern, GlobalRole,
    HistoryEventType, InvitationStatus, MembershipStatus, NotificationType,
    ParticipantCalendarStatus, ReminderType, ScheduleKind, TaskResult,
    WorkspaceKind, WorkspaceLifecycle,
)


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
    memberships: Mapped[list[WorkspaceMember]] = relationship(back_populates="user", foreign_keys="WorkspaceMember.user_id")


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
        _enum_check("lifecycle", WorkspaceLifecycle, "ck_workspaces_lifecycle_valid"),
        CheckConstraint("(lifecycle = 'ACTIVE' AND deactivated_at IS NULL) OR (lifecycle = 'INACTIVE' AND deactivated_at IS NOT NULL)", name="ck_workspaces_lifecycle_consistent"),
        CheckConstraint("kind = 'SHARED' OR lifecycle = 'ACTIVE'", name="ck_workspaces_personal_active"),
        CheckConstraint("lock_version > 0", name="ck_workspaces_lock_version_positive"),
        Index("uq_workspaces_personal_owner", "owner_user_id", unique=True, postgresql_where=text("kind = 'PERSONAL'")),
        Index("ix_workspaces_owner_kind_id", "owner_user_id", "kind", "id"),
        Index("ix_workspaces_owner_lifecycle_kind_id", "owner_user_id", "lifecycle", "kind", "id"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[WorkspaceKind] = mapped_column(String(20), default=WorkspaceKind.PERSONAL, server_default=text("'PERSONAL'"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lifecycle: Mapped[WorkspaceLifecycle] = mapped_column(String(16), default=WorkspaceLifecycle.ACTIVE, server_default=text("'ACTIVE'"), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    members: Mapped[list[WorkspaceMember]] = relationship(back_populates="workspace", passive_deletes=True)
    categories: Mapped[list[Category]] = relationship(back_populates="workspace", passive_deletes=True)


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
    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])


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
    workspace: Mapped[Workspace] = relationship(back_populates="categories")
    master_tasks: Mapped[list[MasterTask]] = relationship(back_populates="category", passive_deletes=True)
    activity_masters: Mapped[list[ActivityMaster]] = relationship(back_populates="category", passive_deletes=True)


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
    category: Mapped[Category] = relationship(back_populates="master_tasks")
    tasks: Mapped[list[Task]] = relationship(back_populates="master_task", passive_deletes=True)


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
    category: Mapped[Category] = relationship(back_populates="activity_masters")


class GenerationBatch(Base):
    __tablename__ = "generation_batches"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "created_by_user_id"], MEMBERSHIP_FK, name="fk_generation_batches_creator_membership", ondelete="RESTRICT"),
        UniqueConstraint("id", "workspace_id", name="uq_generation_batches_id_workspace"),
        _enum_check("entity_type", GenerationEntityType, "ck_generation_batches_entity_type_valid"),
        _enum_check("pattern", GenerationPattern, "ck_generation_batches_pattern_valid"),
        CheckConstraint("date_until >= date_from", name="ck_generation_batches_date_range"),
        CheckConstraint("(pattern = 'DAILY' AND weekdays IS NULL AND month_days IS NULL) OR (pattern = 'WEEKLY' AND weekdays IS NOT NULL AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (pattern = 'MONTHLY' AND month_days IS NOT NULL AND lifemanager_smallint_array_unique_in_range(month_days, 1, 31) AND weekdays IS NULL)", name="ck_generation_batches_recurrence_shape"),
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
    master_task: Mapped[MasterTask] = relationship(back_populates="tasks")


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
        ForeignKeyConstraint(["pending_item_id", "workspace_id"], ["pending_items.id", "pending_items.workspace_id"], name="fk_pending_item_history_item_workspace", ondelete="CASCADE"),
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
    stages: Mapped[list[ProjectStage]] = relationship(back_populates="project", passive_deletes=True)


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
    project: Mapped[Project] = relationship(back_populates="stages")


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
        Index("uq_activities_catalog_occurrence", "workspace_id", "activity_master_id", "organizer_user_id", "starts_at", unique=True, postgresql_where=text("activity_master_id IS NOT NULL")),
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
    participants: Mapped[list[ActivityParticipant]] = relationship(back_populates="activity", cascade="all, delete-orphan", passive_deletes=True)
    reminders: Mapped[list[ActivityReminder]] = relationship(back_populates="activity", cascade="all, delete-orphan", passive_deletes=True)


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
    activity: Mapped[Activity] = relationship(back_populates="participants")


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
    activity: Mapped[Activity] = relationship(back_populates="reminders")


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
        CheckConstraint("(schedule_kind = 'DAILY' AND weekdays IS NULL AND month_days IS NULL) OR (schedule_kind = 'WEEKLY' AND weekdays IS NOT NULL AND lifemanager_smallint_array_unique_in_range(weekdays, 0, 6) AND month_days IS NULL) OR (schedule_kind = 'MONTHLY' AND month_days IS NOT NULL AND lifemanager_smallint_array_unique_in_range(month_days, 1, 31) AND weekdays IS NULL)", name="ck_reminder_preferences_recurrence_shape"),
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
    deliveries: Mapped[list[NotificationDelivery]] = relationship(back_populates="notification", passive_deletes=True)


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
    deliveries: Mapped[list[NotificationDelivery]] = relationship(back_populates="push_subscription", passive_deletes=True)


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
    notification: Mapped[Notification] = relationship(back_populates="deliveries")
    push_subscription: Mapped[PushSubscription] = relationship(back_populates="deliveries")


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        PrimaryKeyConstraint(
            "action",
            "dimension",
            "key_digest",
            "window_start",
            name="pk_rate_limit_buckets",
        ),
        CheckConstraint(
            "length(btrim(action)) > 0",
            name="ck_rate_limit_buckets_action_nonblank",
        ),
        CheckConstraint(
            "length(btrim(dimension)) > 0",
            name="ck_rate_limit_buckets_dimension_nonblank",
        ),
        CheckConstraint(
            "octet_length(key_digest) = 32",
            name="ck_rate_limit_buckets_digest_length",
        ),
        CheckConstraint(
            "attempt_count >= 1",
            name="ck_rate_limit_buckets_attempt_count_positive",
        ),
        CheckConstraint(
            "expires_at > window_start",
            name="ck_rate_limit_buckets_expiry_after_window",
        ),
        Index("ix_rate_limit_buckets_expires_at", "expires_at"),
    )

    action: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension: Mapped[str] = mapped_column(String(16), nullable=False)
    key_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
