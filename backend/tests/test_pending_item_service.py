import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import Category, PendingItem, User, WorkspaceTrackingMetadata
from app.schemas.pending_item import (
    PendingItemCreate,
    PendingItemPlanningUpdate,
    PendingItemState,
    PendingItemTrackingBatch,
)
from app.services.pending_item_service import (
    PendingItemCategoryNotFoundError,
    PendingItemConflictError,
    PendingItemNotFoundError,
    PendingItemVersionConflictError,
    create_pending_item,
    list_pending_items,
    list_review_eligible_pending_items,
    save_pending_item_tracking,
    update_pending_item,
)
from app.services.category_service import _is_used


def _domain(*, active=True, planned=date(2026, 8, 12), progress=0, version=1):
    workspace_id = uuid.uuid4()
    timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud",
        normalized_name="salud", created_at=timestamp, updated_at=timestamp,
    )
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    item = PendingItem(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Control", is_active=active,
        planned_date=planned, progress=progress,
        completion_date=date(2026, 8, 12) if progress == 100 else None,
        comment=None, created_by_id=user.id, lock_version=version,
        created_at=timestamp, updated_at=timestamp,
    )
    return workspace_id, category, user, item


def test_create_sets_approved_defaults_and_never_commits() -> None:
    workspace_id, category, user, _item = _domain()
    db = MagicMock(spec=Session); db.scalar.return_value = category
    item = create_pending_item(
        db, workspace_id=workspace_id, current_user=user,
        item_in=PendingItemCreate(
            category_id=category.id, name="  Control   anual ", is_active=True,
            planned_date=date(2026, 8, 20),
        ),
    )
    assert item.name == "Control anual" and item.progress == 0
    assert item.completion_date is item.comment is None
    assert item.lock_version == 1 and item.created_by_id == user.id
    category_lookup = db.scalar.call_args.args[0]
    assert category_lookup._for_update_arg is not None
    db.add.assert_called_once_with(item); db.flush.assert_called_once_with()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_create_hides_foreign_category_and_normalizes_inactive_date() -> None:
    workspace_id, _category, user, _item = _domain()
    db = MagicMock(spec=Session); db.scalar.return_value = None
    with pytest.raises(PendingItemCategoryNotFoundError):
        create_pending_item(
            db, workspace_id=workspace_id, current_user=user,
            item_in=PendingItemCreate(
                category_id=uuid.uuid4(), name="Control", is_active=False,
                planned_date=date(2026, 8, 20),
            ),
        )


def test_pending_item_reference_participates_in_category_usage_protection() -> None:
    db = MagicMock(spec=Session); db.scalar.return_value = True
    assert _is_used(db, category_id=uuid.uuid4()) is True
    statement = str(db.scalar.call_args.args[0])
    assert "pending_items" in statement
    constraint = next(
        constraint for constraint in PendingItem.__table__.foreign_key_constraints
        if constraint.name == "fk_pending_items_category_workspace"
    )
    assert constraint.ondelete == "RESTRICT"


def test_planning_update_is_cas_and_deactivation_clears_date() -> None:
    workspace_id, category, _user, item = _domain(version=3)
    db = MagicMock(spec=Session); db.scalar.return_value = item
    db.execute.return_value.rowcount = 1
    updated = update_pending_item(
        db, workspace_id=workspace_id, pending_item_id=item.id,
        item_in=PendingItemPlanningUpdate(
            name="Control nuevo", is_active=False, lock_version=3
        ),
    )
    assert updated.name == "Control nuevo" and updated.is_active is False
    assert updated.planned_date is None and updated.lock_version == 4
    assert inspect(updated).attrs.lock_version.history.has_changes() is False
    db.flush.assert_called_once_with(); db.commit.assert_not_called()

    item.lock_version = 4
    db.execute.return_value.rowcount = 0
    with pytest.raises(PendingItemVersionConflictError):
        update_pending_item(
            db, workspace_id=workspace_id, pending_item_id=item.id,
            item_in=PendingItemPlanningUpdate(name="Otro", lock_version=4),
        )


def test_planning_category_change_locks_target_category() -> None:
    workspace_id, _category, _user, item = _domain(version=2)
    target = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Trabajo",
        normalized_name="trabajo",
    )
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [item, target]
    db.execute.return_value.rowcount = 1
    updated = update_pending_item(
        db, workspace_id=workspace_id, pending_item_id=item.id,
        item_in=PendingItemPlanningUpdate(category_id=target.id, lock_version=2),
    )
    assert updated.category_id == target.id and updated.category is target
    category_lookup = db.scalar.call_args_list[1].args[0]
    assert category_lookup._for_update_arg is not None


def test_category_list_filter_does_not_lock_category() -> None:
    workspace_id, category, _user, _item = _domain()
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [category, 0]
    db.scalars.return_value.all.return_value = []
    list_pending_items(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
        page=1, page_size=25, category_id=category.id,
    )
    category_lookup = db.scalar.call_args_list[0].args[0]
    assert category_lookup._for_update_arg is None


def test_activation_requires_date() -> None:
    workspace_id, _category, _user, item = _domain(active=False, planned=None)
    db = MagicMock(spec=Session); db.scalar.return_value = item
    with pytest.raises(PendingItemConflictError):
        update_pending_item(
            db, workspace_id=workspace_id, pending_item_id=item.id,
            item_in=PendingItemPlanningUpdate(is_active=True, lock_version=1),
        )


def test_list_filters_in_database_is_paginated_and_eager() -> None:
    workspace_id, category, _user, item = _domain()
    db = MagicMock(spec=Session); db.scalar.side_effect = [category, 1]
    db.scalars.return_value.all.return_value = [item]
    items, total = list_pending_items(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
        page=2, page_size=25, is_active=True, unfinished=True,
        category_id=category.id,
        state=PendingItemState.NO_INICIADO, planned_from=date(2026, 8, 1),
        planned_to=date(2026, 8, 31),
    )
    assert items == [item] and total == 1
    statement = db.scalars.call_args.args[0]
    assert statement._offset_clause.value == 25 and statement._limit_clause.value == 25
    assert statement._with_options
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_review_eligibility_query_is_scoped_active_unfinished_and_due() -> None:
    workspace_id, _category, _user, item = _domain()
    db = MagicMock(spec=Session); db.scalars.return_value.all.return_value = [item]
    assert list_review_eligible_pending_items(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12)
    ) == [item]
    statement = db.scalars.call_args.args[0]
    values = statement.compile().params.values()
    assert workspace_id in values and 100 in values and date(2026, 8, 12) in values


def test_tracking_batch_updates_rows_completion_and_metadata_atomically() -> None:
    workspace_id, _category, _user, first = _domain(progress=50, version=2)
    _, _, _, second = _domain(progress=100, version=4)
    second.workspace_id = workspace_id
    metadata = WorkspaceTrackingMetadata(workspace_id=workspace_id)
    db = MagicMock(spec=Session)
    db.scalars.return_value.all.return_value = [first, second]
    db.execute.return_value.rowcount = 1
    db.get.return_value = metadata
    timestamp = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    rows, saved_at = save_pending_item_tracking(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
        saved_at=timestamp,
        tracking_in=PendingItemTrackingBatch(items=[
            {"id": first.id, "progress": 100, "comment": "Listo", "lock_version": 2},
            {"id": second.id, "progress": 80, "is_active": False, "lock_version": 4},
        ]),
    )
    assert rows == [first, second] and saved_at == timestamp
    assert first.completion_date == date(2026, 8, 12) and first.lock_version == 3
    assert second.completion_date is None and second.planned_date is None
    assert metadata.pending_items_last_tracking_saved_at == timestamp
    assert db.execute.call_count == 2; db.flush.assert_called_once_with()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_tracking_comment_on_completed_item_preserves_completion_date() -> None:
    workspace_id, _category, _user, item = _domain(progress=100)
    original_date = item.completion_date
    metadata = WorkspaceTrackingMetadata(workspace_id=workspace_id)
    db = MagicMock(spec=Session)
    db.scalars.return_value.all.return_value = [item]
    db.execute.return_value.rowcount = 1
    db.get.return_value = metadata
    save_pending_item_tracking(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 20),
        tracking_in=PendingItemTrackingBatch(items=[
            {"id": item.id, "comment": "Corrección", "lock_version": 1}
        ]),
    )
    assert item.completion_date == original_date


def test_tracking_batch_prevalidation_aborts_before_any_write() -> None:
    workspace_id, _category, _user, item = _domain(version=2)
    db = MagicMock(spec=Session); db.scalars.return_value.all.return_value = [item]
    request = PendingItemTrackingBatch(
        items=[{"id": item.id, "progress": 20, "lock_version": 1}]
    )
    with pytest.raises(PendingItemVersionConflictError):
        save_pending_item_tracking(
            db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
            tracking_in=request,
        )
    db.execute.assert_not_called(); db.get.assert_not_called(); db.flush.assert_not_called()

    db.scalars.return_value.all.return_value = []
    with pytest.raises(PendingItemNotFoundError):
        save_pending_item_tracking(
            db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
            tracking_in=request,
        )
