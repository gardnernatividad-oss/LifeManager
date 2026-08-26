import uuid

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.v2_task import RecurringTaskCreate, TaskCreate, TaskUpdate, TaskVersionRequest


def test_task_create_accepts_only_planning_fields() -> None:
    payload = TaskCreate(master_task_id=uuid.uuid4(), planned_date=date(2026, 9, 1))
    assert payload.responsible_user_id is None
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({"master_task_id": str(uuid.uuid4()), "planned_date": "2026-09-01", "result": "COMPLETED"})


def test_task_update_requires_version_and_an_editable_non_null_field() -> None:
    assert TaskUpdate(planned_date=date(2026, 9, 2), lock_version=1).planned_date == date(2026, 9, 2)
    for payload in ({"lock_version": 1}, {"planned_date": None, "lock_version": 1}):
        with pytest.raises(ValidationError):
            TaskUpdate.model_validate(payload)


def test_task_version_is_positive() -> None:
    with pytest.raises(ValidationError):
        TaskVersionRequest(lock_version=0)


@pytest.mark.parametrize(
    ("pattern", "extra"),
    [("DAILY", {}), ("WEEKLY", {"weekdays": [0, 2]}), ("MONTHLY", {"month_days": [29, 31]})],
)
def test_recurring_task_accepts_each_finite_shape(pattern, extra) -> None:
    value = RecurringTaskCreate.model_validate({"master_task_id": str(uuid.uuid4()), "recurrence": {"pattern": pattern, "date_from": "2026-09-01", "date_until": "2026-10-01", **extra}})
    assert value.recurrence.pattern.value == pattern


@pytest.mark.parametrize("recurrence", [
    {"pattern": "DAILY", "date_from": "2026-09-02", "date_until": "2026-09-01"},
    {"pattern": "WEEKLY", "date_from": "2026-09-01", "date_until": "2026-09-30", "weekdays": []},
    {"pattern": "WEEKLY", "date_from": "2026-09-01", "date_until": "2026-09-30", "weekdays": [0], "month_days": [1]},
    {"pattern": "MONTHLY", "date_from": "2026-09-01", "date_until": "2026-09-30", "month_days": [32]},
    {"pattern": "YEARLY", "date_from": "2026-09-01", "date_until": "2026-09-30"},
])
def test_recurring_task_rejects_invalid_or_unbounded_shapes(recurrence) -> None:
    with pytest.raises(ValidationError):
        RecurringTaskCreate.model_validate({"master_task_id": str(uuid.uuid4()), "recurrence": recurrence})
