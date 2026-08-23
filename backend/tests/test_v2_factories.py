from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    GlobalRole,
    MembershipStatus,
    ParticipantCalendarStatus,
)
from tests.factories.v2 import DEFAULT_TODAY, V2Factory, normalized_name


def factory() -> tuple[V2Factory, MagicMock]:
    db = MagicMock(spec=Session)
    return V2Factory(db), db


def test_user_factories_cover_all_account_states_and_global_admin() -> None:
    values, db = factory()
    users = [values.user(status.value.lower(), status=status) for status in AccountStatus]
    admin = values.user("global-admin", global_admin=True)

    assert {user.account_status for user in users} == set(AccountStatus)
    assert users[0].email.endswith("@example.test")
    assert users[0].hashed_password != "Fixture-only password 123!"
    assert admin.global_role is GlobalRole.GLOBAL_ADMIN
    assert db.commit.call_count == 0
    assert db.rollback.call_count == 0


def test_personal_and_shared_workspace_scenarios_have_valid_owners_and_privacy() -> None:
    values, _ = factory()
    personal = values.personal_workspace()
    shared = values.shared_workspace()

    assert personal.workspace.owner_user_id == personal.user.id
    assert personal.owner_membership.user_id == personal.user.id
    assert personal.owner_membership.status is MembershipStatus.ACTIVE
    assert shared.workspace.owner_user_id == shared.owner.id
    assert len(shared.memberships) == 4
    assert {membership.calendar_visibility for membership in shared.memberships} == set(CalendarVisibility)


def test_membership_lifecycle_preserves_historical_rows() -> None:
    values, _ = factory()
    personal = values.personal_workspace()
    left = values.membership(personal.workspace, values.user("left"), status=MembershipStatus.LEFT)
    removed = values.membership(personal.workspace, values.user("removed"), status=MembershipStatus.REMOVED)

    assert left.ended_at is not None
    assert removed.ended_at is not None


def test_normalization_preserves_accents_and_normalizes_case_and_spacing() -> None:
    assert normalized_name("  ALIMENTACIO\N{COMBINING ACUTE ACCENT}N  ") == "alimentación"
    assert normalized_name("Tecnología") != normalized_name("Tecnologia")


def test_canonical_dataset_is_small_coherent_and_flush_only() -> None:
    values, db = factory()
    dataset = values.build_canonical_dataset()

    shared = dataset.shared_workspace
    owner, member_a, member_b, _ = (shared.owner, *shared.members)
    same_master_date = [
        task for task in dataset.tasks
        if task.master_task_id == dataset.master_tasks[0].id
        and task.planned_date == DEFAULT_TODAY + timedelta(days=1)
    ]

    assert len(dataset.users) == 4
    assert len(dataset.personal_workspaces) == 3
    assert len(same_master_date) == 2
    assert {task.responsible_user_id for task in same_master_date} == {member_a.id, member_b.id}
    assert sum(stage.weight for stage in dataset.project_stages) == Decimal("100.00")
    assert dataset.participants[-1].calendar_status is ParticipantCalendarStatus.REMOVED
    assert dataset.activity_reminders[-1].is_enabled is False
    assert dataset.review_metadata[0].user_id == owner.id
    assert dataset.review_metadata[0].tasks_last_saved_at != dataset.review_metadata[1].tasks_last_saved_at
    assert dataset.pending_items[-1].is_active is False
    assert dataset.pending_items[-1].planned_date is None
    assert dataset.pending_history[0].recorded_at < dataset.pending_history[1].recorded_at
    assert db.flush.call_count >= 1
    assert db.commit.call_count == 0
    assert db.rollback.call_count == 0


def test_default_factories_do_not_build_invalid_cross_workspace_assignments() -> None:
    values, _ = factory()
    personal = values.personal_workspace()
    category = values.category(personal.workspace, "Personal")
    master = values.master_task(personal.workspace, category, "Comprar alimentos")
    task = values.task(personal.workspace, master, personal.user, personal.user, date(2026, 2, 1))

    assert task.workspace_id == master.workspace_id == category.workspace_id
    assert task.responsible_user_id == personal.owner_membership.user_id
