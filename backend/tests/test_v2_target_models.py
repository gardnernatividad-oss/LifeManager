from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint

from app.models import (
    AccountActionToken, Activity, ActivityParticipant, ActivityReminder, Category,
    GenerationBatch, NotificationDelivery, PendingItemHistory, ProjectStage,
    ProjectStageHistory, ReminderPreference, Task, UserReviewMetadata, Workspace,
    WorkspaceMember,
)
from app.models.base import Base


EXPECTED_TABLES = {
    "users", "user_account_state_events", "account_action_tokens", "workspaces",
    "workspace_members", "workspace_invitations", "categories", "master_tasks",
    "activity_masters", "generation_batches", "tasks", "pending_items",
    "pending_item_history", "projects", "project_leader_history", "project_stages",
    "project_stage_history", "activities", "activity_participants",
    "activity_reminders", "user_review_metadata", "reminder_preferences",
    "notifications", "push_subscriptions", "notification_deliveries",
    "rate_limit_buckets",
}


def names(table, type_):
    return {item.name for item in (*table.constraints, *table.indexes) if isinstance(item, type_)}


def test_metadata_contains_exactly_the_v2_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert "project_steps" not in Base.metadata.tables
    assert "workspace_tracking_metadata" not in Base.metadata.tables


def test_workspace_and_membership_invariants_are_structural() -> None:
    assert "uq_workspaces_personal_owner" in names(Workspace.__table__, Index)
    assert "uq_workspace_members_workspace_user" in names(WorkspaceMember.__table__, UniqueConstraint)
    assert "uq_workspace_members_id_workspace" in names(WorkspaceMember.__table__, UniqueConstraint)
    assert "ck_workspace_members_lifecycle_consistent" in names(WorkspaceMember.__table__, CheckConstraint)


def test_task_occurrence_and_same_workspace_constraints_exist() -> None:
    uniques = names(Task.__table__, UniqueConstraint)
    foreign_keys = names(Task.__table__, ForeignKeyConstraint)
    assert "uq_tasks_workspace_master_date_responsible" in uniques
    assert {"fk_tasks_master_task_workspace", "fk_tasks_responsible_membership", "fk_tasks_creator_membership"} <= foreign_keys
    assert "ck_tasks_resolution_consistent" in names(Task.__table__, CheckConstraint)


def test_catalog_and_generation_shapes_are_constrained() -> None:
    assert "uq_categories_workspace_normalized_name" in names(Category.__table__, UniqueConstraint)
    assert "ck_generation_batches_recurrence_shape" in names(GenerationBatch.__table__, CheckConstraint)
    assert "ck_generation_batches_timezone_shape" in names(GenerationBatch.__table__, CheckConstraint)
    generation_shape = next(
        constraint for constraint in GenerationBatch.__table__.constraints
        if constraint.name == "ck_generation_batches_recurrence_shape"
    )
    reminder_shape = next(
        constraint for constraint in ReminderPreference.__table__.constraints
        if constraint.name == "ck_reminder_preferences_recurrence_shape"
    )
    assert "weekdays IS NOT NULL" in str(generation_shape.sqltext)
    assert "month_days IS NOT NULL" in str(generation_shape.sqltext)
    assert "weekdays IS NOT NULL" in str(reminder_shape.sqltext)
    assert "month_days IS NOT NULL" in str(reminder_shape.sqltext)


def test_progress_weight_participant_and_reminder_constraints_exist() -> None:
    assert "ck_project_stages_weight_range" in names(ProjectStage.__table__, CheckConstraint)
    assert "ck_project_stages_progress_range" in names(ProjectStage.__table__, CheckConstraint)
    assert "uq_activity_participants_activity_user" in names(ActivityParticipant.__table__, UniqueConstraint)
    assert "uq_activity_reminders_activity_user" in names(ActivityReminder.__table__, UniqueConstraint)
    assert "uq_reminder_preferences_user_type" in names(ReminderPreference.__table__, UniqueConstraint)


def test_history_and_review_tables_have_the_approved_immutable_shape() -> None:
    for model in (PendingItemHistory, ProjectStageHistory):
        assert "updated_at" not in model.__table__.columns
        assert "lock_version" not in model.__table__.columns
    assert list(UserReviewMetadata.__table__.primary_key.columns.keys()) == ["user_id"]
    assert {"tasks_last_saved_at", "pending_items_last_saved_at", "project_stages_last_saved_at"} <= set(UserReviewMetadata.__table__.columns.keys())


def test_tokens_activity_and_delivery_safety_constraints_exist() -> None:
    assert "uq_account_action_tokens_digest" in names(AccountActionToken.__table__, UniqueConstraint)
    assert "ck_account_tokens_terminal_exclusive" in names(AccountActionToken.__table__, CheckConstraint)
    assert "ck_activities_source_xor" in names(Activity.__table__, CheckConstraint)
    assert "ck_activities_time_range" in names(Activity.__table__, CheckConstraint)
    assert "uq_notification_deliveries_notification_subscription" in names(NotificationDelivery.__table__, UniqueConstraint)


def test_mutable_entities_have_positive_version_defaults() -> None:
    for table_name in (
        "users", "workspaces", "workspace_members", "categories", "master_tasks",
        "activity_masters", "tasks", "pending_items", "projects", "project_stages",
        "activities", "activity_participants", "activity_reminders", "reminder_preferences",
    ):
        column = Base.metadata.tables[table_name].c.lock_version
        assert str(column.server_default.arg) == "1"
