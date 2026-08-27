import uuid

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.v2_activity import ActivityCreate, ActivityUpdate


def test_activity_create_requires_aware_valid_range_and_unique_participants() -> None:
    start = datetime(2026, 9, 1, 15, tzinfo=timezone.utc)
    participant = uuid.uuid4()
    value = ActivityCreate(activity_master_id=uuid.uuid4(), participant_user_ids=[participant], starts_at=start, ends_at=start + timedelta(hours=1))
    assert value.starts_at.tzinfo is not None
    for payload in (
        {"activity_master_id": uuid.uuid4(), "starts_at": start.replace(tzinfo=None), "ends_at": start + timedelta(hours=1)},
        {"activity_master_id": uuid.uuid4(), "starts_at": start, "ends_at": start},
        {"activity_master_id": uuid.uuid4(), "participant_user_ids": [participant, participant], "starts_at": start, "ends_at": start + timedelta(hours=1)},
    ):
        with pytest.raises(ValidationError):
            ActivityCreate.model_validate(payload)


def test_activity_update_is_strict_versioned_and_rejects_mass_assignment() -> None:
    assert ActivityUpdate(participant_user_ids=[], lock_version=1).participant_user_ids == []
    with pytest.raises(ValidationError):
        ActivityUpdate(lock_version=1)
    with pytest.raises(ValidationError):
        ActivityUpdate.model_validate({"starts_at": "2026-09-01T10:00:00Z", "lock_version": 1, "workspace_id": str(uuid.uuid4()), "can_edit": True})
