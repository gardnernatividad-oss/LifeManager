import uuid

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Category, MasterTask, PendingItem, Project, ProjectStep, Task, TaskResult,
    User, WorkspaceTrackingMetadata,
)
from app.schemas.review import ReviewSave
from app.services.review_service import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewVersionConflictError,
    _lock_project_steps,
    get_review,
    save_review,
)


def _domain():
    workspace_id = uuid.uuid4(); now = datetime.now(timezone.utc)
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    category = Category(id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud")
    master = MasterTask(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Correr", normalized_name="correr",
    )
    task = Task(
        id=uuid.uuid4(), workspace_id=workspace_id, master_task_id=master.id,
        master_task=master, planned_date=date(2026, 8, 11), result=None,
        lock_version=1, created_at=now, updated_at=now,
    )
    pending = PendingItem(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Control", is_active=True,
        planned_date=date(2026, 8, 12), progress=50, completion_date=None,
        comment="Pendiente", lock_version=2, created_at=now, updated_at=now,
    )
    project = Project(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Mudanza", is_active=True, lock_version=1,
        created_at=now, updated_at=now,
    )
    step = ProjectStep(
        id=uuid.uuid4(), project_id=project.id, project=project, name="Empacar",
        planned_date=date(2026, 8, 10), weight=Decimal("100"), progress=25,
        completion_date=None, comment=None, position=0, lock_version=3,
        created_at=now, updated_at=now,
    )
    project.steps = [step]
    return workspace_id, user, task, pending, project, step


def test_get_review_queries_only_eligible_scoped_rows_and_does_not_write() -> None:
    workspace_id, _user, task, pending, _project, step = _domain()
    metadata = WorkspaceTrackingMetadata(
        workspace_id=workspace_id,
        last_review_saved_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
    )
    db = MagicMock(spec=Session)
    db.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[task])),
        MagicMock(all=MagicMock(return_value=[pending])),
        MagicMock(all=MagicMock(return_value=[step])),
    ]
    db.get.return_value = metadata
    result = get_review(db, workspace_id=workspace_id, local_date=date(2026, 8, 12))
    assert result == ([task], [pending], [step], metadata.last_review_saved_at)
    for call in db.scalars.call_args_list:
        statement = call.args[0]
        assert workspace_id in statement.compile().params.values()
    db.execute.assert_not_called(); db.flush.assert_not_called(); db.commit.assert_not_called()


def test_save_review_updates_all_sections_and_only_review_timestamp() -> None:
    workspace_id, user, task, pending, project, step = _domain()
    metadata = WorkspaceTrackingMetadata(
        workspace_id=workspace_id,
        pending_items_last_tracking_saved_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    project_timestamp = datetime(2026, 8, 2, tzinfo=timezone.utc)
    project.last_tracking_saved_at = project_timestamp
    db = MagicMock(spec=Session)
    db.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[task])),
        MagicMock(all=MagicMock(return_value=[pending])),
        MagicMock(all=MagicMock(return_value=[step])),
        MagicMock(all=MagicMock(return_value=[project])),
        MagicMock(all=MagicMock(return_value=[step])),
    ]
    db.execute.return_value.rowcount = 1; db.get.return_value = metadata
    saved_at = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    result = save_review(
        db, workspace_id=workspace_id, current_user=user,
        local_date=date(2026, 8, 12), saved_at=saved_at,
        review_in=ReviewSave(
            tasks=[{"id": task.id, "result": "COMPLETED", "lock_version": 1}],
            pending_items=[{"id": pending.id, "progress": 100, "comment": "Listo", "lock_version": 2}],
            project_steps=[{"id": step.id, "progress": 100, "comment": "Listo", "lock_version": 3}],
        ),
    )
    assert result == saved_at and db.execute.call_count == 3
    task_values = db.execute.call_args_list[0].args[0].compile().params.values()
    assert TaskResult.COMPLETED in task_values and user.id in task_values and saved_at in task_values
    assert date(2026, 8, 12) in db.execute.call_args_list[1].args[0].compile().params.values()
    assert date(2026, 8, 12) in db.execute.call_args_list[2].args[0].compile().params.values()
    assert metadata.last_review_saved_at == saved_at
    assert metadata.pending_items_last_tracking_saved_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert project.last_tracking_saved_at == project_timestamp
    db.flush.assert_called_once_with(); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_review_locks_projects_before_steps_in_deterministic_order() -> None:
    workspace_id, _user, _task, _pending, first_project, first_step = _domain()
    second_project = Project(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=first_project.category_id,
        name="Segundo", is_active=True, lock_version=1,
    )
    second_step = ProjectStep(
        id=uuid.uuid4(), project_id=second_project.id, name="Paso",
        planned_date=date(2026, 8, 12), weight=Decimal("100"), progress=0,
        position=0, lock_version=1,
    )
    projects = sorted([first_project, second_project], key=lambda item: str(item.id))
    steps = sorted([first_step, second_step], key=lambda item: (str(item.project_id), str(item.id)))
    db = MagicMock(spec=Session)
    db.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[first_step, second_step])),
        MagicMock(all=MagicMock(return_value=projects)),
        MagicMock(all=MagicMock(return_value=steps)),
    ]
    result = _lock_project_steps(
        db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
        review_in=ReviewSave(project_steps=[
            {"id": first_step.id, "progress": 20, "lock_version": first_step.lock_version},
            {"id": second_step.id, "comment": "x", "lock_version": second_step.lock_version},
        ]),
    )
    assert result == steps
    identify, project_lock, step_lock = [call.args[0] for call in db.scalars.call_args_list]
    assert identify._for_update_arg is None
    assert project_lock._for_update_arg is not None
    assert step_lock._for_update_arg is not None
    assert "projects.id" in str(project_lock._order_by_clause)
    assert "project_steps.project_id" in str(step_lock._order_by_clause)
    assert "project_steps.id" in str(step_lock._order_by_clause)
    db.execute.assert_not_called(); db.flush.assert_not_called()


def test_missing_or_inactive_project_aborts_before_step_lock_or_update() -> None:
    workspace_id, _user, _task, _pending, project, step = _domain()
    request = ReviewSave(project_steps=[
        {"id": step.id, "progress": 50, "lock_version": step.lock_version}
    ])
    for projects, error in (([], ReviewNotFoundError), ([project], ReviewConflictError)):
        project.is_active = False
        db = MagicMock(spec=Session)
        db.scalars.side_effect = [
            MagicMock(all=MagicMock(return_value=[step])),
            MagicMock(all=MagicMock(return_value=projects)),
        ]
        with pytest.raises(error):
            _lock_project_steps(
                db, workspace_id=workspace_id, local_date=date(2026, 8, 12),
                review_in=request,
            )
        assert db.scalars.call_count == 2
        db.execute.assert_not_called(); db.flush.assert_not_called()


def test_empty_review_is_meaningful_and_updates_only_last_review() -> None:
    workspace_id, user, *_ = _domain(); metadata = WorkspaceTrackingMetadata(workspace_id=workspace_id)
    db = MagicMock(spec=Session); db.get.return_value = metadata
    saved = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    assert save_review(
        db, workspace_id=workspace_id, current_user=user,
        local_date=date(2026, 8, 12), review_in=ReviewSave(), saved_at=saved,
    ) == saved
    assert metadata.last_review_saved_at == saved
    db.scalars.assert_not_called(); db.execute.assert_not_called(); db.flush.assert_called_once_with()


@pytest.mark.parametrize("invalid", ["task", "pending", "step"])
def test_ineligible_row_is_rejected_before_updates(invalid) -> None:
    workspace_id, user, task, pending, project, step = _domain()
    request = ReviewSave(
        tasks=[{"id": task.id, "result": "NOT_COMPLETED", "lock_version": 1}],
        pending_items=[{"id": pending.id, "comment": "x", "lock_version": 2}],
        project_steps=[{"id": step.id, "comment": "x", "lock_version": 3}],
    )
    if invalid == "task": task.planned_date = date(2026, 8, 13)
    elif invalid == "pending": pending.is_active = False
    else: project.is_active = False
    db = MagicMock(spec=Session)
    db.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[task])),
        MagicMock(all=MagicMock(return_value=[pending])),
        MagicMock(all=MagicMock(return_value=[step])),
        MagicMock(all=MagicMock(return_value=[project])),
    ]
    with pytest.raises(ReviewConflictError):
        save_review(
            db, workspace_id=workspace_id, current_user=user,
            local_date=date(2026, 8, 12), review_in=request,
        )
    db.execute.assert_not_called(); db.get.assert_not_called(); db.flush.assert_not_called()


def test_missing_or_stale_across_sections_aborts_before_updates() -> None:
    workspace_id, user, task, pending, _project, _step = _domain()
    request = ReviewSave(
        tasks=[{"id": task.id, "result": "COMPLETED", "lock_version": 1}],
        pending_items=[{"id": pending.id, "progress": 60, "lock_version": 1}],
    )
    db = MagicMock(spec=Session)
    db.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[task])),
        MagicMock(all=MagicMock(return_value=[pending])),
    ]
    with pytest.raises(ReviewVersionConflictError):
        save_review(
            db, workspace_id=workspace_id, current_user=user,
            local_date=date(2026, 8, 12), review_in=request,
        )
    db.execute.assert_not_called(); db.flush.assert_not_called()

    db = MagicMock(spec=Session)
    db.scalars.return_value.all.return_value = []
    with pytest.raises(ReviewNotFoundError):
        save_review(
            db, workspace_id=workspace_id, current_user=user,
            local_date=date(2026, 8, 12),
            review_in=ReviewSave(tasks=[{"id": task.id, "result": "COMPLETED", "lock_version": 1}]),
        )
