import uuid

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.task import (
    BulkTaskPattern,
    TaskBulkCreate,
    TaskBulkDelete,
    TaskCreate,
    TaskUpdate,
)


def test_individual_create_accepts_only_master_task_and_date() -> None:
    payload = {"master_task_id": str(uuid.uuid4()), "planned_date": "2026-08-20"}
    assert TaskCreate.model_validate(payload).planned_date == date(2026, 8, 20)
    for field in (
        "workspace_id",
        "title",
        "description",
        "category_id",
        "project_id",
        "result",
        "status",
        "scheduled_at",
        "task_series_id",
        "pattern",
    ):
        with pytest.raises(ValidationError):
            TaskCreate.model_validate({**payload, field: "unexpected"})


def test_update_requires_date_and_expected_version() -> None:
    assert TaskUpdate(planned_date=date(2026, 8, 21), lock_version=1).lock_version == 1
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate({"planned_date": "2026-08-21"})
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate({"planned_date": "2026-08-21", "lock_version": 0})


def test_bulk_range_and_weekdays_are_strict() -> None:
    master_task_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="start_date"):
        TaskBulkCreate(
            master_task_id=master_task_id,
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
            pattern=BulkTaskPattern.DAILY,
        )
    with pytest.raises(ValidationError, match="at least one weekday"):
        TaskBulkCreate(
            master_task_id=master_task_id,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            pattern=BulkTaskPattern.WEEKLY,
            weekdays=[],
        )
    with pytest.raises(ValidationError, match="Monday=0"):
        TaskBulkCreate(
            master_task_id=master_task_id,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            pattern=BulkTaskPattern.WEEKLY,
            weekdays=[7],
        )
    with pytest.raises(ValidationError):
        TaskBulkCreate.model_validate(
            {
                "master_task_id": master_task_id,
                "start_date": "2026-08-01",
                "end_date": "2026-09-01",
                "pattern": "MONTHLY",
            }
        )


def test_bulk_delete_rejects_duplicate_ids() -> None:
    task_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="unique"):
        TaskBulkDelete.model_validate(
            {"items": [{"id": task_id, "lock_version": 1}, {"id": task_id, "lock_version": 1}]}
        )
