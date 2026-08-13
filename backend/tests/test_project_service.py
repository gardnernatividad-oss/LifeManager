import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import Category, Project, ProjectStep, User
from app.schemas.project import (
    ProjectCreate,
    ProjectGeneralTrackingUpdate,
    ProjectPlanningUpdate,
    ProjectState,
    ProjectStepCreate,
    ProjectStepPlanningUpdate,
    ProjectTrackingBatch,
)
from app.services.project_service import (
    ProjectCategoryNotFoundError,
    ProjectConflictError,
    ProjectStepNotFoundError,
    ProjectVersionConflictError,
    create_project,
    create_project_step,
    list_projects,
    list_review_eligible_project_steps,
    save_project_tracking,
    update_project,
    update_project_general_tracking,
    update_project_step,
)


def _domain(*, active=False, version=1):
    workspace_id = uuid.uuid4(); timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Personal",
        normalized_name="personal", created_at=timestamp, updated_at=timestamp,
    )
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    project = Project(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Mudanza", is_active=active,
        general_comment=None, last_tracking_saved_at=None,
        created_by_id=user.id, lock_version=version,
        created_at=timestamp, updated_at=timestamp,
    )
    project.steps = []
    return workspace_id, category, user, project


def _step(project, *, position=0, progress=0, weight=Decimal("100"), version=1):
    timestamp = datetime.now(timezone.utc)
    step = ProjectStep(
        id=uuid.uuid4(), project_id=project.id, name="Empacar",
        planned_date=date(2026, 8, 12), weight=weight, progress=progress,
        completion_date=date(2026, 8, 12) if progress == 100 else None,
        comment=None, position=position, lock_version=version,
        created_at=timestamp, updated_at=timestamp,
    )
    project.steps.append(step)
    return step


def test_create_locks_category_and_sets_defaults() -> None:
    workspace_id, category, user, _project = _domain()
    db = MagicMock(spec=Session); db.scalar.return_value = category
    project = create_project(
        db, workspace_id=workspace_id, current_user=user,
        project_in=ProjectCreate(
            category_id=category.id, name=" Mudanza ", is_active=True,
            steps=[{"name": "Empacar", "planned_date": "2026-08-12",
                    "weight": "100.00", "position": 0}],
        ),
    )
    assert project.created_by_id == user.id and project.lock_version == 1
    assert project.general_comment is project.last_tracking_saved_at is None
    assert project.steps[0].progress == 0 and project.steps[0].lock_version == 1
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    db.add.assert_called_once_with(project); db.flush.assert_called_once_with()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "steps",
    [[], [{"name": "A", "position": 0}],
     [{"name": "A", "planned_date": "2026-08-12", "weight": "99", "position": 0}]],
)
def test_active_creation_rejects_invalid_structure(steps) -> None:
    workspace_id, category, user, _project = _domain()
    db = MagicMock(spec=Session); db.scalar.return_value = category
    with pytest.raises(ProjectConflictError):
        create_project(
            db, workspace_id=workspace_id, current_user=user,
            project_in=ProjectCreate(
                category_id=category.id, name="P", is_active=True, steps=steps,
            ),
        )
    db.add.assert_not_called(); db.flush.assert_not_called()


def test_foreign_category_is_hidden_and_category_change_locks_target() -> None:
    workspace_id, _category, _user, project = _domain(version=2)
    db = MagicMock(spec=Session); db.scalar.return_value = None
    with pytest.raises(ProjectCategoryNotFoundError):
        create_project(
            db, workspace_id=workspace_id, current_user=User(id=uuid.uuid4()),
            project_in=ProjectCreate(
                category_id=uuid.uuid4(), name="P", is_active=False,
            ),
        )
    target = Category(id=uuid.uuid4(), workspace_id=workspace_id, name="T", normalized_name="t")
    db = MagicMock(spec=Session); db.scalar.side_effect = [project, target]
    db.execute.return_value.rowcount = 1
    updated = update_project(
        db, workspace_id=workspace_id, project_id=project.id,
        project_in=ProjectPlanningUpdate(category_id=target.id, lock_version=2),
    )
    assert updated.category is target
    assert db.scalar.call_args_list[1].args[0]._for_update_arg is not None


def test_activation_validates_exact_structure_and_project_cas() -> None:
    workspace_id, _category, _user, project = _domain(version=3)
    db = MagicMock(spec=Session); db.scalar.return_value = project
    with pytest.raises(ProjectConflictError):
        update_project(
            db, workspace_id=workspace_id, project_id=project.id,
            project_in=ProjectPlanningUpdate(is_active=True, lock_version=3),
        )
    _step(project)
    db.execute.return_value.rowcount = 1
    updated = update_project(
        db, workspace_id=workspace_id, project_id=project.id,
        project_in=ProjectPlanningUpdate(is_active=True, lock_version=3),
    )
    assert updated.is_active is True and updated.lock_version == 4
    assert db.scalar.call_args.args[0]._for_update_arg is not None
    db.flush.assert_called_once_with()


def test_inactive_step_creation_and_update_preserve_tracking_fields() -> None:
    workspace_id, _category, _user, project = _domain()
    db = MagicMock(spec=Session); db.scalar.return_value = project
    step = create_project_step(
        db, workspace_id=workspace_id, project_id=project.id,
        step_in=ProjectStepCreate(name="Empacar", position=0),
    )
    assert step.progress == 0 and step.completion_date is step.comment is None
    assert db.scalar.call_args.args[0]._for_update_arg is not None

    project.steps = [step]; db.reset_mock(); db.scalar.return_value = project
    db.execute.return_value.rowcount = 1
    result = update_project_step(
        db, workspace_id=workspace_id, project_id=project.id, step_id=step.id,
        step_in=ProjectStepPlanningUpdate(
            name="Empacar cajas", planned_date=date(2026, 8, 20),
            weight=Decimal("100"), position=1, lock_version=1,
        ),
    )
    assert result.name == "Empacar cajas" and result.progress == 0
    assert result.comment is None and result.lock_version == 2


def test_active_project_structure_edit_is_blocked_and_foreign_step_hidden() -> None:
    workspace_id, _category, _user, project = _domain(active=True)
    step = _step(project)
    db = MagicMock(spec=Session); db.scalar.return_value = project
    with pytest.raises(ProjectConflictError):
        create_project_step(
            db, workspace_id=workspace_id, project_id=project.id,
            step_in=ProjectStepCreate(name="Otro", position=1),
        )
    project.is_active = False
    with pytest.raises(ProjectStepNotFoundError):
        update_project_step(
            db, workspace_id=workspace_id, project_id=project.id,
            step_id=uuid.uuid4(),
            step_in=ProjectStepPlanningUpdate(name="Otro", lock_version=1),
        )


def test_list_is_filtered_eager_paginated_and_urgent() -> None:
    workspace_id, category, _user, project = _domain()
    db = MagicMock(spec=Session); db.scalar.side_effect = [category, 1]
    db.scalars.return_value.all.return_value = [project]
    items, total = list_projects(
        db, workspace_id=workspace_id, page=2, page_size=25,
        is_active=False, category_id=category.id, state=ProjectState.NO_INICIADO,
        planned_from=date(2026, 8, 1), planned_to=date(2026, 8, 31),
    )
    assert items == [project] and total == 1
    statement = db.scalars.call_args.args[0]
    assert statement._offset_clause.value == 25 and statement._limit_clause.value == 25
    assert statement._with_options and db.scalar.call_args_list[0].args[0]._for_update_arg is None


def test_general_comment_update_does_not_change_tracking_timestamp() -> None:
    workspace_id, _category, _user, project = _domain(version=2)
    original = project.last_tracking_saved_at
    db = MagicMock(spec=Session); db.scalar.return_value = project
    db.execute.return_value.rowcount = 1
    updated = update_project_general_tracking(
        db, workspace_id=workspace_id, project_id=project.id,
        project_in=ProjectGeneralTrackingUpdate(
            general_comment="Comentario", lock_version=2
        ),
    )
    assert updated.general_comment == "Comentario"
    assert updated.last_tracking_saved_at is original and updated.lock_version == 3


def test_tracking_batch_is_atomic_sets_completion_and_timestamp() -> None:
    workspace_id, _category, _user, project = _domain(active=True, version=4)
    first = _step(project, position=0, progress=50, weight=Decimal("40"), version=2)
    second = _step(project, position=1, progress=100, weight=Decimal("60"), version=3)
    db = MagicMock(spec=Session); db.scalar.return_value = project
    db.scalars.return_value.all.return_value = [first, second]
    db.execute.return_value.rowcount = 1
    timestamp = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    result, saved_at = save_project_tracking(
        db, workspace_id=workspace_id, project_id=project.id,
        local_date=date(2026, 8, 12), saved_at=timestamp,
        tracking_in=ProjectTrackingBatch(project_lock_version=4, items=[
            {"id": first.id, "progress": 100, "comment": "Listo", "lock_version": 2},
            {"id": second.id, "progress": 80, "lock_version": 3},
        ]),
    )
    assert result is project and saved_at == timestamp
    assert first.completion_date == date(2026, 8, 12)
    assert second.completion_date is None
    assert first.lock_version == 3 and second.lock_version == 4
    assert project.last_tracking_saved_at == timestamp and project.lock_version == 5
    assert db.execute.call_count == 3; db.flush.assert_called_once_with()
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_inactive_project_tracking_is_rejected_before_any_write() -> None:
    workspace_id, _category, _user, project = _domain(active=False, version=2)
    step = _step(project, progress=50, version=3)
    original_timestamp = project.last_tracking_saved_at
    db = MagicMock(spec=Session); db.scalar.return_value = project
    with pytest.raises(ProjectConflictError, match="Inactive"):
        save_project_tracking(
            db, workspace_id=workspace_id, project_id=project.id,
            local_date=date(2026, 8, 12),
            tracking_in=ProjectTrackingBatch(project_lock_version=2, items=[
                {"id": step.id, "progress": 100, "lock_version": 3}
            ]),
        )
    assert project.last_tracking_saved_at is original_timestamp
    assert project.lock_version == 2 and step.lock_version == 3
    db.scalars.assert_not_called(); db.execute.assert_not_called()
    db.flush.assert_not_called(); db.commit.assert_not_called()


def test_tracking_comment_only_preserves_completion_date_and_stale_aborts_writes() -> None:
    workspace_id, _category, _user, project = _domain(active=True, version=1)
    step = _step(project, progress=100, version=2); original = step.completion_date
    db = MagicMock(spec=Session); db.scalar.return_value = project
    db.scalars.return_value.all.return_value = [step]
    db.execute.return_value.rowcount = 1
    save_project_tracking(
        db, workspace_id=workspace_id, project_id=project.id,
        local_date=date(2026, 8, 20),
        tracking_in=ProjectTrackingBatch(project_lock_version=1, items=[
            {"id": step.id, "comment": "Corrección", "lock_version": 2}
        ]),
    )
    assert step.completion_date == original

    project.lock_version = 1; step.lock_version = 2; db.reset_mock()
    db.scalar.return_value = project; db.scalars.return_value.all.return_value = [step]
    with pytest.raises(ProjectVersionConflictError):
        save_project_tracking(
            db, workspace_id=workspace_id, project_id=project.id,
            local_date=date(2026, 8, 20),
            tracking_in=ProjectTrackingBatch(project_lock_version=1, items=[
                {"id": step.id, "progress": 50, "lock_version": 1}
            ]),
        )
    db.execute.assert_not_called(); db.flush.assert_not_called()


def test_review_eligibility_is_workspace_active_unfinished_and_due() -> None:
    workspace_id, _category, _user, project = _domain(active=True)
    step = _step(project)
    db = MagicMock(spec=Session); db.scalars.return_value.all.return_value = [step]
    assert list_review_eligible_project_steps(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12)
    ) == [step]
    values = db.scalars.call_args.args[0].compile().params.values()
    assert workspace_id in values and 100 in values and date(2026, 8, 12) in values
