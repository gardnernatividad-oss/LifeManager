import uuid

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import Category, Project, ProjectStep
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailRead,
    ProjectState,
    ProjectStepPlanningUpdate,
    ProjectTrackingBatch,
    StepCompliance,
    derive_project_values,
    derive_step_compliance,
    derive_step_state,
)


def _project(progresses=(0, 0), weights=(Decimal("40"), Decimal("60"))):
    workspace_id = uuid.uuid4(); timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Personal",
        normalized_name="personal", created_at=timestamp, updated_at=timestamp,
    )
    project = Project(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Mudanza", is_active=True, general_comment=None,
        last_tracking_saved_at=None, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )
    project.steps = [
        ProjectStep(
            id=uuid.uuid4(), project_id=project.id, name=f"Paso {index}",
            planned_date=date(2026, 8, 10 + index), weight=weight,
            progress=progress, completion_date=None, comment=None,
            position=index, lock_version=1, created_at=timestamp, updated_at=timestamp,
        )
        for index, (progress, weight) in enumerate(zip(progresses, weights))
    ]
    return project


def test_create_is_strict_cleans_names_and_validates_positions() -> None:
    value = ProjectCreate(
        category_id=uuid.uuid4(), name="  Proyecto   familiar ", is_active=False,
        steps=[{"name": "  Primer   paso ", "position": 0}],
    )
    assert value.name == "Proyecto familiar" and value.steps[0].name == "Primer paso"
    with pytest.raises(ValidationError):
        ProjectCreate(category_id=uuid.uuid4(), name=" ", is_active=False)
    with pytest.raises(ValidationError):
        ProjectCreate(
            category_id=uuid.uuid4(), name="P", is_active=False,
            steps=[{"name": "A", "position": 0}, {"name": "B", "position": 0}],
        )


def test_planning_and_tracking_step_fields_are_separated() -> None:
    with pytest.raises(ValidationError):
        ProjectStepPlanningUpdate(progress=50, lock_version=1)
    with pytest.raises(ValidationError):
        ProjectTrackingBatch(project_lock_version=1, items=[{
            "id": uuid.uuid4(), "name": "Otro", "lock_version": 1,
        }])
    with pytest.raises(ValidationError):
        ProjectTrackingBatch(project_lock_version=1, items=[{
            "id": uuid.uuid4(), "progress": 101, "lock_version": 1,
        }])


@pytest.mark.parametrize(
    ("progress", "state"),
    [(0, ProjectState.NO_INICIADO), (1, ProjectState.EN_PROCESO),
     (99, ProjectState.EN_PROCESO), (100, ProjectState.FINALIZADO)],
)
def test_step_state(progress, state) -> None:
    assert derive_step_state(progress) is state


@pytest.mark.parametrize(
    ("progresses", "progress", "state"),
    [
        ((0, 0), Decimal("0"), ProjectState.NO_INICIADO),
        ((25, 50), Decimal("40"), ProjectState.EN_PROCESO),
        ((100, 100), Decimal("100"), ProjectState.FINALIZADO),
    ],
)
def test_project_date_progress_and_state_are_derived(progresses, progress, state) -> None:
    project = _project(progresses=progresses)
    planned, actual, derived_state, total = derive_project_values(project)
    assert planned == date(2026, 8, 11)
    assert actual == progress and derived_state is state and total == Decimal("100")


def test_incomplete_inactive_project_has_no_progress_or_state() -> None:
    project = _project(progresses=(0,), weights=(None,))
    project.is_active = False
    planned, progress, state, total = derive_project_values(project)
    assert planned == date(2026, 8, 10)
    assert progress is state is None and total == 0


@pytest.mark.parametrize(
    ("planned", "completed", "today", "compliance", "days"),
    [
        (date(2026, 8, 15), None, date(2026, 8, 12), StepCompliance.EN_PLAZO, 3),
        (date(2026, 8, 10), None, date(2026, 8, 11), StepCompliance.ATRASADO, 1),
        (date(2026, 8, 10), date(2026, 8, 8), date(2026, 8, 12), StepCompliance.CON_ADELANTO, 2),
        (date(2026, 8, 10), date(2026, 8, 10), date(2026, 8, 12), StepCompliance.A_TIEMPO, 0),
        (date(2026, 8, 10), date(2026, 8, 13), date(2026, 8, 14), StepCompliance.CON_RETRASO, 3),
    ],
)
def test_step_compliance(planned, completed, today, compliance, days) -> None:
    step = _project(progresses=(100,), weights=(Decimal("100"),)).steps[0]
    step.planned_date = planned; step.completion_date = completed
    assert derive_step_compliance(step, local_date=today) == (compliance, days)


def test_detail_serializes_category_steps_and_derived_values() -> None:
    payload = ProjectDetailRead.from_project(_project(), local_date=date(2026, 8, 12))
    assert payload.category.name == "Personal" and len(payload.steps) == 2
    assert payload.planned_date == date(2026, 8, 11) and payload.total_weight == 100

