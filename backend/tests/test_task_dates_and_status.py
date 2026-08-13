import uuid

from datetime import date, datetime, timezone

import pytest

from app.core.dates import local_today
from app.models import Task, TaskResult
from app.schemas.task import TaskStatus, derive_task_status


def _task(planned_date: date, result: TaskResult | None = None) -> Task:
    return Task(id=uuid.uuid4(), planned_date=planned_date, result=result)


@pytest.mark.parametrize(
    ("planned_date", "result", "expected"),
    [
        (date(2026, 8, 13), None, TaskStatus.PROGRAMADA),
        (date(2026, 8, 12), None, TaskStatus.PENDIENTE),
        (date(2026, 8, 1), None, TaskStatus.PENDIENTE),
        (date(2026, 8, 13), TaskResult.COMPLETED, TaskStatus.COMPLETADA),
        (date(2026, 8, 13), TaskResult.NOT_COMPLETED, TaskStatus.NO_REALIZADA),
    ],
)
def test_public_status_is_derived(planned_date, result, expected) -> None:
    assert derive_task_status(_task(planned_date, result), local_date=date(2026, 8, 12)) is expected


def test_local_today_uses_iana_timezone_across_utc_boundary() -> None:
    instant = datetime(2026, 8, 12, 2, 0, tzinfo=timezone.utc)
    assert local_today("America/Lima", now=instant) == date(2026, 8, 11)
    assert local_today("Pacific/Kiritimati", now=instant) == date(2026, 8, 12)
    assert local_today("Pacific/Honolulu", now=instant) == date(2026, 8, 11)


def test_timezone_boundary_changes_task_status() -> None:
    instant = datetime(2026, 8, 12, 2, 0, tzinfo=timezone.utc)
    task = _task(date(2026, 8, 12))
    assert derive_task_status(task, local_date=local_today("America/Lima", now=instant)) is TaskStatus.PROGRAMADA
    assert derive_task_status(task, local_date=local_today("Pacific/Kiritimati", now=instant)) is TaskStatus.PENDIENTE
