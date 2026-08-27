import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import Activity, ActivityParticipant, User, Workspace, WorkspaceMember
from app.models.enums import ActivityStatus, ParticipantCalendarStatus, WorkspaceKind
from app.schemas.v2_activity import ActivityUpdate
from app.services.v2_activity import ActivityConflictError, ActivityNotFoundError, delete_activity, get_activity, leave_activity, temporal_state, update_activity
from app.services.v2_workspace import WorkspaceAccess


NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def scope() -> tuple[WorkspaceAccess, User]:
    actor = User(id=uuid.uuid4(), email="actor@test.local")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=actor.id, kind=WorkspaceKind.SHARED, name="Casa")
    return WorkspaceAccess(workspace, WorkspaceMember(workspace_id=workspace.id, user_id=actor.id)), actor


def activity(access: WorkspaceAccess, *, start: datetime, generated: bool = False) -> Activity:
    return Activity(id=uuid.uuid4(), workspace_id=access.workspace.id, organizer_user_id=access.workspace.owner_user_id, activity_master_id=uuid.uuid4(), title="Reunión", starts_at=start, ends_at=start + timedelta(hours=1), status=ActivityStatus.SCHEDULED, generation_batch_id=uuid.uuid4() if generated else None, lock_version=2)


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
        item.lock_version = 2; db.scalar.return_value = participant; db.scalars.return_value = []
        assert leave_activity(db, access=access, actor=actor, activity_id=item.id, expected_version=2) is item
        assert participant.calendar_status == ParticipantCalendarStatus.REMOVED
        item.lock_version = 2
        delete_activity(db, access=access, activity_id=item.id, expected_version=2)
    db.delete.assert_called_once_with(item)


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
