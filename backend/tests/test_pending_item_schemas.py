import uuid

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import Category, PendingItem
from app.schemas.pending_item import (
    PendingItemCompliance,
    PendingItemCreate,
    PendingItemPlanningUpdate,
    PendingItemRead,
    PendingItemState,
    PendingItemTrackingBatch,
    derive_pending_item_compliance,
    derive_pending_item_state,
)


def _item(*, planned_date=date(2026, 8, 10), progress=0, completion_date=None):
    workspace_id = uuid.uuid4()
    timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud",
        normalized_name="salud", created_at=timestamp, updated_at=timestamp,
    )
    return PendingItem(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Chequeo médico", is_active=True,
        planned_date=planned_date, progress=progress,
        completion_date=completion_date, comment=None, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )


def test_create_cleans_name_and_enforces_active_date() -> None:
    item = PendingItemCreate(
        category_id=uuid.uuid4(), name="  Control   médico ", is_active=True,
        planned_date=date(2026, 8, 12),
    )
    assert item.name == "Control médico"
    with pytest.raises(ValidationError):
        PendingItemCreate(category_id=uuid.uuid4(), name=" ", is_active=False)
    with pytest.raises(ValidationError):
        PendingItemCreate(category_id=uuid.uuid4(), name="Control", is_active=True)


def test_planning_and_tracking_schemas_are_strictly_separated() -> None:
    with pytest.raises(ValidationError):
        PendingItemPlanningUpdate(lock_version=1, progress=50)
    with pytest.raises(ValidationError):
        PendingItemTrackingBatch(
            items=[{"id": uuid.uuid4(), "lock_version": 1, "planned_date": "2026-08-12"}]
        )
    with pytest.raises(ValidationError):
        PendingItemTrackingBatch(items=[{"id": uuid.uuid4(), "lock_version": 1, "progress": 101}])
    with pytest.raises(ValidationError):
        PendingItemTrackingBatch(items=[{"id": uuid.uuid4(), "lock_version": 1, "progress": None}])
    with pytest.raises(ValidationError):
        PendingItemTrackingBatch(items=[{"id": uuid.uuid4(), "lock_version": 1}])


@pytest.mark.parametrize(
    ("progress", "expected"),
    [(0, PendingItemState.NO_INICIADO), (1, PendingItemState.EN_PROCESO),
     (99, PendingItemState.EN_PROCESO), (100, PendingItemState.FINALIZADO)],
)
def test_state_is_derived(progress, expected) -> None:
    assert derive_pending_item_state(progress) is expected


@pytest.mark.parametrize(
    ("planned", "completed", "today", "compliance", "days"),
    [
        (date(2026, 8, 15), None, date(2026, 8, 12), PendingItemCompliance.EN_PLAZO, 3),
        (date(2026, 8, 10), None, date(2026, 8, 11), PendingItemCompliance.ATRASADO, 1),
        (date(2026, 8, 10), date(2026, 8, 8), date(2026, 8, 12), PendingItemCompliance.CON_ADELANTO, 2),
        (date(2026, 8, 10), date(2026, 8, 10), date(2026, 8, 12), PendingItemCompliance.A_TIEMPO, 0),
        (date(2026, 8, 10), date(2026, 8, 13), date(2026, 8, 14), PendingItemCompliance.CON_RETRASO, 3),
    ],
)
def test_compliance_and_detail_are_derived(planned, completed, today, compliance, days) -> None:
    item = _item(planned_date=planned, progress=100 if completed else 50, completion_date=completed)
    assert derive_pending_item_compliance(item, local_date=today) == (compliance, days)


def test_inactive_without_date_has_no_misleading_compliance_and_read_is_nested() -> None:
    item = _item(planned_date=None)
    item.is_active = False
    assert derive_pending_item_compliance(item, local_date=date(2026, 8, 12)) == (None, None)
    payload = PendingItemRead.from_pending_item(item, local_date=date(2026, 8, 12))
    assert payload.category.name == "Salud"
    assert payload.compliance is None and payload.detail_days is None
