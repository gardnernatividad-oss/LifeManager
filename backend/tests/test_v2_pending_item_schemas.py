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


def test_tracking_accepts_comment_only_and_cleans_unicode_text() -> None:
    value = PendingItemProgressUpdate(comment="  Información recibida  ", lock_version=2)
    assert value.progress is None and value.comment == "Información recibida"
    with pytest.raises(ValidationError):
        PendingItemProgressUpdate(comment="   ", lock_version=2)
    with pytest.raises(ValidationError):
        PendingItemProgressUpdate(lock_version=2)


def test_tracking_and_correction_reject_hostile_history_fields() -> None:
    for schema, progress in ((PendingItemProgressUpdate, 50), (PendingItemCorrection, 50)):
        with pytest.raises(ValidationError):
            schema.model_validate({"progress": progress, "lock_version": 1, "actor_user_id": str(uuid.uuid4()), "type": "CORRECTION"})
