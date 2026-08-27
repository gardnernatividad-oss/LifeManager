import uuid

import pytest
from pydantic import ValidationError

from app.schemas.v2_pending_item import PendingItemCorrection, PendingItemCreate, PendingItemProgressUpdate, PendingItemUpdate


def test_create_cleans_name_and_forbids_internal_fields() -> None:
    value = PendingItemCreate(category_id=uuid.uuid4(), name="  Compra   grande ", planned_date="2026-09-01")
    assert value.name == "Compra grande"
    with pytest.raises(ValidationError):
        PendingItemCreate.model_validate({"category_id": str(uuid.uuid4()), "name": "X", "planned_date": "2026-09-01", "workspace_id": str(uuid.uuid4())})


@pytest.mark.parametrize("value", [-1, 101])
def test_progress_bounds(value: int) -> None:
    with pytest.raises(ValidationError):
        PendingItemProgressUpdate(progress=value, lock_version=1)


def test_correction_cannot_finalize_and_update_is_strict() -> None:
    with pytest.raises(ValidationError):
        PendingItemCorrection(progress=100, lock_version=1)
    with pytest.raises(ValidationError):
        PendingItemUpdate.model_validate({"lock_version": 1})
    with pytest.raises(ValidationError):
        PendingItemUpdate.model_validate({"name": "X", "lock_version": 1, "completion_date": "2026-09-01"})
