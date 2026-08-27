import uuid

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.models import Category, PendingItem, PendingItemHistory, User, Workspace, WorkspaceMember
from app.models.enums import HistoryEventType, WorkspaceKind
from app.schemas.v2_pending_item import PendingItemCreate, PendingItemUpdate
from app.services.v2_pending_item import PendingItemConflictError, correct_pending_item, create_pending_item, deactivate_pending_item, delete_pending_item, list_pending_item_history, pending_item_projection, reactivate_pending_item, update_pending_item, update_pending_progress
from app.services.v2_workspace import WorkspaceAccess


def context(kind=WorkspaceKind.SHARED):
    actor = User(id=uuid.uuid4(), email="ana@example.com", hashed_password="hash", first_name="Ana", last_name="Uno")
    workspace = Workspace(id=uuid.uuid4(), name="Casa", kind=kind, owner_user_id=actor.id)
    return actor, WorkspaceAccess(workspace, WorkspaceMember(workspace_id=workspace.id, user_id=actor.id))


def item(access, actor, *, progress=0, active=True):
    return PendingItem(id=uuid.uuid4(), workspace_id=access.workspace.id, category_id=uuid.uuid4(), responsible_user_id=actor.id, name="Compra", is_active=active, planned_date=date(2026, 9, 10) if active else None, progress=progress, completion_date=date(2026, 9, 9) if progress == 100 else None, created_by_user_id=actor.id, lock_version=1)


@patch("app.services.v2_pending_item._responsible")
@patch("app.services.v2_pending_item._category")
def test_create_derives_context_and_initial_state(category, responsible) -> None:
    actor, access = context()
    target = uuid.uuid4()
    created = create_pending_item(db := MagicMock(), access=access, actor=actor, item_in=PendingItemCreate(category_id=uuid.uuid4(), responsible_user_id=target, name="Compra", planned_date=date(2026, 9, 10)))
    assert created.workspace_id == access.workspace.id and created.responsible_user_id == target
    assert created.progress == 0 and created.is_active is True and created.completion_date is None
    db.add.assert_called_once_with(created)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


@patch("app.services.v2_pending_item._responsible")
@patch("app.services.v2_pending_item._category")
def test_personal_creation_uses_owner(category, responsible) -> None:
    actor, access = context(WorkspaceKind.PERSONAL)
    created = create_pending_item(MagicMock(), access=access, actor=actor, item_in=PendingItemCreate(category_id=uuid.uuid4(), responsible_user_id=uuid.uuid4(), name="Compra", planned_date=date(2026, 9, 10)))
    assert created.responsible_user_id == actor.id


@patch("app.services.v2_pending_item._item")
def test_progress_completion_and_history_are_atomic(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=50)
    lookup.return_value = current
    updated = update_pending_progress(db := MagicMock(), access=access, actor=actor, pending_item_id=current.id, progress=100, expected_version=1, local_date=date(2026, 9, 12))
    assert updated.progress == 100 and updated.completion_date == date(2026, 9, 12)
    assert updated.is_active is True and updated.lock_version == 2
    history = db.add.call_args.args[0]
    assert isinstance(history, PendingItemHistory) and history.event_type == HistoryEventType.TRACKING
    db.flush.assert_called_once()
    db.commit.assert_not_called()


@patch("app.services.v2_pending_item._item")
def test_comment_only_versions_item_and_creates_one_tracking_entry(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=40)
    lookup.return_value = current
    update_pending_progress(db := MagicMock(), access=access, actor=actor, pending_item_id=current.id, progress=None, comment="Avance validado", expected_version=1, local_date=date(2026, 9, 12))
    assert current.progress == 40 and current.lock_version == 2
    history = db.add.call_args.args[0]
    assert history.progress == 40 and history.comment == "Avance validado" and history.event_type == HistoryEventType.TRACKING
    db.add.assert_called_once(); db.flush.assert_called_once()


@patch("app.services.v2_pending_item._item")
def test_progress_and_comment_create_one_atomic_tracking_entry(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=40)
    lookup.return_value = current
    update_pending_progress(db := MagicMock(), access=access, actor=actor, pending_item_id=current.id, progress=60, comment="Información recibida", expected_version=1, local_date=date(2026, 9, 12))
    history = db.add.call_args.args[0]
    assert current.progress == 60 and history.progress == 60 and history.comment == "Información recibida"
    db.add.assert_called_once()


@patch("app.services.v2_pending_item._item")
def test_finalized_is_read_only_except_explicit_correction(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=100)
    lookup.return_value = current
    with pytest.raises(PendingItemConflictError):
        update_pending_item(MagicMock(), access=access, pending_item_id=current.id, item_in=PendingItemUpdate(name="Otro", lock_version=1))
    with pytest.raises(PendingItemConflictError):
        update_pending_progress(MagicMock(), access=access, actor=actor, pending_item_id=current.id, progress=50, expected_version=1, local_date=date(2026, 9, 12))


@patch("app.services.v2_pending_item._item")
def test_correction_reopens_and_preserves_history_boundary(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=100)
    lookup.return_value = current
    corrected = correct_pending_item(db := MagicMock(), access=access, actor=actor, pending_item_id=current.id, progress=0, expected_version=1)
    assert corrected.progress == 0 and corrected.completion_date is None and corrected.is_active is True
    assert db.add.call_args.args[0].event_type == HistoryEventType.CORRECTION
    assert db.add.call_args.args[0].progress == 0


@patch("app.services.v2_pending_item._item")
def test_history_is_newest_first_with_deterministic_tiebreaker(lookup) -> None:
    actor, access = context()
    lookup.return_value = item(access, actor)
    db = MagicMock()
    expected = [(PendingItemHistory(), actor)]
    db.execute.return_value.all.return_value = expected
    assert list_pending_item_history(db, workspace_id=access.workspace.id, pending_item_id=lookup.return_value.id) == expected
    statement = db.execute.call_args.args[0]
    assert "recorded_at DESC" in str(statement) and "pending_item_history.id DESC" in str(statement)


@patch("app.services.v2_pending_item._item")
def test_lifecycle_clears_and_requires_date(lookup) -> None:
    actor, access = context()
    current = item(access, actor, progress=20)
    lookup.return_value = current
    deactivate_pending_item(db := MagicMock(), access=access, pending_item_id=current.id, expected_version=1)
    assert current.is_active is False and current.planned_date is None
    current.lock_version = 2
    reactivate_pending_item(db, access=access, pending_item_id=current.id, planned_date=date(2026, 10, 1), expected_version=2)
    assert current.is_active is True and current.planned_date == date(2026, 10, 1)


@pytest.mark.parametrize("progress, allowed", [(0, True), (1, False), (100, False)])
@patch("app.services.v2_pending_item._item")
def test_delete_is_decided_under_lock_by_current_progress(lookup, progress, allowed) -> None:
    actor, access = context()
    current = item(access, actor, progress=progress)
    lookup.return_value = current
    db = MagicMock()
    if allowed:
        delete_pending_item(db, access=access, pending_item_id=current.id, expected_version=1)
        db.delete.assert_called_once_with(current)
    else:
        with pytest.raises(PendingItemConflictError):
            delete_pending_item(db, access=access, pending_item_id=current.id, expected_version=1)
        db.delete.assert_not_called()
    assert lookup.call_args.kwargs["lock"] is True


@pytest.mark.parametrize("progress, active, expected", [(0, True, ("NO_INICIADO", True, False, True)), (50, True, ("EN_PROCESO", True, False, False)), (100, True, ("FINALIZADO", False, True, False)), (0, False, ("NO_INICIADO", False, False, True))])
def test_projection_derives_state_compliance_and_capabilities(progress, active, expected) -> None:
    actor, access = context()
    current = item(access, actor, progress=progress, active=active)
    category = Category(id=current.category_id, workspace_id=current.workspace_id, name="Casa", normalized_name="casa")
    db = MagicMock()
    db.scalar.side_effect = [category, actor]
    projection = pending_item_projection(db, item=current, local_date=date(2026, 9, 8))
    assert (projection[2], projection[5], projection[7], projection[10]) == expected


@pytest.mark.parametrize("completion, today, expected", [(None, date(2026, 9, 8), ("EN_PLAZO", 2)), (None, date(2026, 9, 12), ("ATRASADO", 2)), (date(2026, 9, 10), date(2026, 9, 12), ("A_TIEMPO", 0)), (date(2026, 9, 8), date(2026, 9, 12), ("CON_ADELANTO", 2)), (date(2026, 9, 12), date(2026, 9, 12), ("CON_RETRASO", 2))])
def test_projection_derives_calendar_day_compliance(completion, today, expected) -> None:
    actor, access = context()
    current = item(access, actor, progress=100 if completion else 50)
    current.planned_date = date(2026, 9, 10)
    current.completion_date = completion
    category = Category(id=current.category_id, workspace_id=current.workspace_id, name="Casa", normalized_name="casa")
    db = MagicMock(); db.scalar.side_effect = [category, actor]
    projection = pending_item_projection(db, item=current, local_date=today)
    assert projection[3:5] == expected
