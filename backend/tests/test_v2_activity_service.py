import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import Activity, ActivityParticipant, ActivityReminder, GenerationBatch, User, Workspace, WorkspaceMember
from app.models.enums import ActivityStatus, ParticipantCalendarStatus, WorkspaceKind
from app.schemas.v2_activity import ActivityCreate, ActivityUpdate, RecurringActivityCreate
from app.services.v2_activity import ActivityConflictError, ActivityNotFoundError, _mutation_scope_activities, _set_participants, create_activity, create_recurring_activities, delete_activity, get_activity, leave_activity, temporal_state, update_activity
from app.services.v2_workspace import WorkspaceAccess


NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def scope() -> tuple[WorkspaceAccess, User]:
    actor = User(id=uuid.uuid4(), email="actor@test.local")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=actor.id, kind=WorkspaceKind.SHARED, name="Casa")
    return WorkspaceAccess(workspace, WorkspaceMember(workspace_id=workspace.id, user_id=actor.id)), actor


def activity(access: WorkspaceAccess, *, start: datetime, generated: bool = False) -> Activity:
    return Activity(id=uuid.uuid4(), workspace_id=access.workspace.id, organizer_user_id=access.workspace.owner_user_id, activity_master_id=uuid.uuid4(), title="Reunión", starts_at=start, ends_at=start + timedelta(hours=1), status=ActivityStatus.SCHEDULED, generation_batch_id=uuid.uuid4() if generated else None, lock_version=2)


@patch("app.services.v2_activity._now", return_value=NOW)
@patch("app.services.v2_activity._eligible_users")
@patch("app.services.v2_activity._category")
def test_custom_activity_preserves_real_name_and_manual_category(category, users, now) -> None:
    access, actor = scope()
    category_id = uuid.uuid4()
    category.return_value.id = category_id
    created = create_activity(MagicMock(), access=access, actor=actor, activity_in=ActivityCreate(custom_name="  Cita   médica ", custom_category_id=category_id, starts_at=NOW + timedelta(days=1), ends_at=NOW + timedelta(days=1, hours=1)))
    assert created.activity_master_id is None
    assert created.title == "Cita médica"
    assert created.custom_category_id == category_id


@patch("app.services.v2_activity._now", return_value=NOW)
@patch("app.services.v2_activity._eligible_users")
@patch("app.services.v2_activity._category")
def test_recurring_custom_activities_share_batch_and_source(category, users, now) -> None:
    access, actor = scope()
    category_id = uuid.uuid4()
    category.return_value.id = category_id
    db = MagicMock()
    db.scalar.return_value = None
    db.flush.side_effect = lambda: setattr(db.add.call_args.args[0], "id", uuid.uuid4()) if getattr(db.add.call_args.args[0], "id", None) is None else None
    payload = RecurringActivityCreate.model_validate({"custom_name": "Cita médica", "custom_category_id": str(category_id), "start_time": "15:00", "end_time": "16:00", "timezone": "America/Lima", "recurrence": {"pattern": "DAILY", "date_from": "2026-09-03", "date_until": "2026-09-04"}})
    created = create_recurring_activities(db, access=access, actor=actor, activity_in=payload)
    assert len(created) == 2
    assert len({item.generation_batch_id for item in created}) == 1
    assert all(item.activity_master_id is None and item.title == "Cita médica" and item.custom_category_id == category_id for item in created)


@pytest.mark.parametrize(("start", "expected"), ((NOW + timedelta(hours=1), "FUTURE"), (NOW - timedelta(minutes=30), "IN_PROGRESS"), (NOW - timedelta(hours=2), "PAST")))
def test_temporal_state_uses_start_and_end_boundaries(start, expected) -> None:
    access, _ = scope()
    assert temporal_state(activity(access, start=start), now=NOW) == expected


@pytest.mark.parametrize("start", (NOW, NOW - timedelta(minutes=30), NOW - timedelta(hours=2)))
def test_started_activity_rejects_edit_delete_and_leave_before_writes(start) -> None:
    access, actor = scope(); item = activity(access, start=start); db = MagicMock()
    with patch("app.services.v2_activity._activity", return_value=item), patch("app.services.v2_activity._now", return_value=NOW):
        with pytest.raises(ActivityConflictError): update_activity(db, access=access, activity_id=item.id, activity_in=ActivityUpdate(ends_at=NOW + timedelta(hours=3), lock_version=2))
        with pytest.raises(ActivityConflictError): delete_activity(db, access=access, activity_id=item.id, expected_version=2)
        with pytest.raises(ActivityConflictError): leave_activity(db, access=access, actor=actor, activity_id=item.id, expected_version=2)
    db.flush.assert_not_called(); db.delete.assert_not_called(); db.add.assert_not_called()


def test_future_activity_is_editable_deletable_and_participant_can_leave() -> None:
    access, actor = scope(); item = activity(access, start=NOW + timedelta(hours=2)); participant = ActivityParticipant(id=uuid.uuid4(), activity_id=item.id, workspace_id=item.workspace_id, user_id=actor.id, calendar_status=ParticipantCalendarStatus.VISIBLE, lock_version=1); db = MagicMock()
    with patch("app.services.v2_activity._activity", return_value=item), patch("app.services.v2_activity._now", return_value=NOW), patch("app.services.v2_activity._flush"):
        assert update_activity(db, access=access, activity_id=item.id, activity_in=ActivityUpdate(ends_at=item.ends_at + timedelta(hours=1), lock_version=2)).lock_version == 3
        item.lock_version = 2; db.scalar.return_value = participant; db.scalars.side_effect = [[participant], [], []]
        assert leave_activity(db, access=access, actor=actor, activity_id=item.id, expected_version=2) is item
        assert participant.calendar_status == ParticipantCalendarStatus.REMOVED
        item.lock_version = 2
        delete_activity(db, access=access, actor=actor, activity_id=item.id, expected_version=2)
    db.delete.assert_not_called()
    assert item.status == ActivityStatus.CANCELLED


def test_boundary_is_revalidated_after_activity_lock() -> None:
    access, _ = scope(); item = activity(access, start=NOW); db = MagicMock(); db.scalar.return_value = item
    with patch("app.services.v2_activity._now", return_value=NOW):
        with pytest.raises(ActivityConflictError):
            update_activity(db, access=access, activity_id=item.id, activity_in=ActivityUpdate(ends_at=item.ends_at + timedelta(hours=1), lock_version=2))
    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is not None
    db.flush.assert_not_called()


def test_activity_lookup_is_scoped_by_workspace_and_hides_foreign_ids() -> None:
    access, _ = scope(); db = MagicMock(); db.scalar.return_value = None
    with pytest.raises(ActivityNotFoundError):
        get_activity(db, workspace_id=access.workspace.id, activity_id=uuid.uuid4())
    sql = str(db.scalar.call_args.args[0])
    assert "activities.id" in sql and "activities.workspace_id" in sql


def test_generated_this_is_mutable_but_standalone_rejects_future_scope() -> None:
    access, _ = scope(); generated = activity(access, start=NOW + timedelta(days=1), generated=True)
    with patch("app.services.v2_activity._activity", return_value=generated), patch("app.services.v2_activity._now", return_value=NOW), patch("app.services.v2_activity._flush"):
        updated = update_activity(MagicMock(), access=access, activity_id=generated.id,
                                  activity_in=ActivityUpdate(ends_at=generated.ends_at + timedelta(minutes=30), lock_version=2))
    assert updated.lock_version == 3

    standalone = activity(access, start=NOW + timedelta(days=1))
    with patch("app.services.v2_activity._activity", return_value=standalone), pytest.raises(ActivityConflictError):
        _mutation_scope_activities(MagicMock(), workspace_id=access.workspace.id, activity_id=standalone.id,
                                   scope="THIS_AND_FUTURE", now=NOW)


def test_generated_future_scope_propagates_local_time_and_organizer_without_touching_history() -> None:
    access, _ = scope()
    selected = activity(access, start=datetime(2026, 9, 7, 14, tzinfo=timezone.utc), generated=True)
    future = activity(access, start=datetime(2026, 9, 14, 14, tzinfo=timezone.utc), generated=True)
    historical = activity(access, start=datetime(2026, 8, 31, 14, tzinfo=timezone.utc), generated=True)
    organizer_id = uuid.uuid4()
    batch = GenerationBatch(id=selected.generation_batch_id, workspace_id=access.workspace.id, timezone="America/Lima")
    db = MagicMock()
    update = ActivityUpdate(
        organizer_user_id=organizer_id,
        starts_at=datetime(2026, 9, 7, 15, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 7, 17, tzinfo=timezone.utc),
        lock_version=2,
        scope="THIS_AND_FUTURE",
    )
    with (
        patch("app.services.v2_activity._now", return_value=NOW),
        patch("app.services.v2_activity._mutation_scope_activities", return_value=(selected, [selected, future], batch)),
        patch("app.services.v2_activity._eligible_users"),
        patch("app.services.v2_activity._flush"),
    ):
        update_activity(db, access=access, activity_id=selected.id, activity_in=update)
    assert (selected.starts_at.hour, selected.ends_at.hour) == (15, 17)
    assert (future.starts_at.hour, future.ends_at.hour) == (15, 17)
    assert selected.organizer_user_id == future.organizer_user_id == organizer_id
    assert historical.starts_at == datetime(2026, 8, 31, 14, tzinfo=timezone.utc)
    assert historical.organizer_user_id == access.workspace.owner_user_id


def test_generated_future_scope_rejects_calendar_date_shift_before_flush() -> None:
    access, _ = scope(); selected = activity(access, start=datetime(2026, 9, 7, 14, tzinfo=timezone.utc), generated=True)
    batch = GenerationBatch(id=selected.generation_batch_id, workspace_id=access.workspace.id, timezone="America/Lima")
    db = MagicMock()
    update = ActivityUpdate(starts_at=datetime(2026, 9, 8, 15, tzinfo=timezone.utc),
                            ends_at=datetime(2026, 9, 8, 16, tzinfo=timezone.utc), lock_version=2,
                            scope="THIS_AND_FUTURE")
    with patch("app.services.v2_activity._now", return_value=NOW), patch(
        "app.services.v2_activity._mutation_scope_activities", return_value=(selected, [selected], batch)
    ), pytest.raises(ActivityConflictError):
        update_activity(db, access=access, activity_id=selected.id, activity_in=update)
    db.flush.assert_not_called()


def test_participant_propagation_removes_only_requested_users_and_their_reminders() -> None:
    access, actor = scope()
    other_id = uuid.uuid4()
    first = activity(access, start=NOW + timedelta(days=1), generated=True)
    second = activity(access, start=NOW + timedelta(days=2), generated=True)
    participants = [
        ActivityParticipant(activity_id=item.id, workspace_id=item.workspace_id, user_id=user_id,
                            calendar_status=ParticipantCalendarStatus.VISIBLE, lock_version=1)
        for item in (first, second) for user_id in (actor.id, other_id)
    ]
    reminders = [
        ActivityReminder(activity_id=item.id, workspace_id=item.workspace_id, user_id=user_id,
                         minutes_before=60, is_enabled=True, lock_version=1)
        for item in (first, second) for user_id in (actor.id, other_id)
    ]
    db = MagicMock(); db.scalars.side_effect = [participants, reminders]
    _set_participants(db, activities=[first, second], requested={other_id}, changed_at=NOW)
    own = [item for item in participants if item.user_id == actor.id]
    others = [item for item in participants if item.user_id == other_id]
    assert all(item.calendar_status == ParticipantCalendarStatus.REMOVED for item in own)
    assert all(item.calendar_status == ParticipantCalendarStatus.VISIBLE for item in others)
    assert all(not item.is_enabled for item in reminders if item.user_id == actor.id)
    assert all(item.is_enabled for item in reminders if item.user_id == other_id)


def test_personal_future_scope_hard_deletes_all_affected_and_shared_scope_cancels() -> None:
    access, actor = scope()
    selected = activity(access, start=NOW + timedelta(days=1), generated=True)
    future = activity(access, start=NOW + timedelta(days=2), generated=True)
    with patch("app.services.v2_activity._now", return_value=NOW), patch(
        "app.services.v2_activity._mutation_scope_activities", return_value=(selected, [selected, future], MagicMock())
    ), patch("app.services.v2_activity._flush"):
        shared_db = MagicMock()
        reminder = ActivityReminder(activity_id=selected.id, workspace_id=selected.workspace_id,
                                    user_id=actor.id, minutes_before=30, is_enabled=True, lock_version=1)
        shared_db.scalars.return_value = [reminder]
        delete_activity(shared_db, access=access, actor=actor, activity_id=selected.id,
                        expected_version=2, scope="THIS_AND_FUTURE")
        assert all(item.status == ActivityStatus.CANCELLED for item in (selected, future))
        assert reminder.is_enabled is False and reminder.lock_version == 2
        shared_db.delete.assert_not_called()

        access.workspace.kind = WorkspaceKind.PERSONAL
        selected.status = future.status = ActivityStatus.SCHEDULED
        selected.lock_version = 2
        personal_db = MagicMock()
        delete_activity(personal_db, access=access, actor=actor, activity_id=selected.id,
                        expected_version=2, scope="THIS_AND_FUTURE")
        assert personal_db.delete.call_count == 2


def test_participant_future_scope_removes_only_actor_and_disables_own_reminders() -> None:
    access, actor = scope()
    selected = activity(access, start=NOW + timedelta(days=1), generated=True)
    future = activity(access, start=NOW + timedelta(days=2), generated=True)
    participants = [ActivityParticipant(activity_id=item.id, workspace_id=item.workspace_id, user_id=actor.id,
                                        calendar_status=ParticipantCalendarStatus.VISIBLE, lock_version=1) for item in (selected, future)]
    reminders = [ActivityReminder(activity_id=item.id, workspace_id=item.workspace_id, user_id=actor.id,
                                  minutes_before=30, is_enabled=True, lock_version=1) for item in (selected, future)]
    db = MagicMock(); db.scalars.side_effect = [participants, reminders]
    with patch("app.services.v2_activity._now", return_value=NOW), patch(
        "app.services.v2_activity._mutation_scope_activities", return_value=(selected, [selected, future], MagicMock())
    ), patch("app.services.v2_activity._flush"):
        leave_activity(db, access=access, actor=actor, activity_id=selected.id,
                       expected_version=2, scope="THIS_AND_FUTURE")
    assert all(item.calendar_status == ParticipantCalendarStatus.REMOVED for item in participants)
    assert all(not item.is_enabled for item in reminders)
    assert "activity_reminders.user_id" in str(db.scalars.call_args_list[1].args[0])
