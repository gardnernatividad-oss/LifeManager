import uuid

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value

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


class ProjectNotFoundError(LookupError):
    pass


class ProjectStepNotFoundError(LookupError):
    pass


class ProjectCategoryNotFoundError(LookupError):
    pass


class ProjectConflictError(ValueError):
    pass


class ProjectVersionConflictError(ValueError):
    pass


_STEP_POSITION_CONSTRAINT = "uq_project_steps_project_id_position"


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        if _constraint_name(error) == _STEP_POSITION_CONSTRAINT:
            raise ProjectConflictError("Project Step position already exists") from error
        raise


def _project_options():
    return (selectinload(Project.category), selectinload(Project.steps))


def _get_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    for_update: bool = False,
) -> Category:
    statement = select(Category).where(
        Category.id == category_id,
        Category.workspace_id == workspace_id,
    )
    if for_update:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None:
        raise ProjectCategoryNotFoundError("Category not found")
    return category


def _get_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    for_update: bool = False,
) -> Project:
    statement = (
        select(Project)
        .options(*_project_options())
        .where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if for_update:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise ProjectNotFoundError("Project not found")
    return project


def _validate_active_structure(steps: list[ProjectStep]) -> None:
    if not steps:
        raise ProjectConflictError("Active Projects require at least one Step")
    if any(step.planned_date is None or step.weight is None for step in steps):
        raise ProjectConflictError("Active Project Steps require dates and weights")
    total = sum((step.weight for step in steps if step.weight is not None), Decimal("0"))
    if total != Decimal("100.00"):
        raise ProjectConflictError("Project Step weights must total exactly 100")


def _new_step(project: Project, step_in: ProjectStepCreate) -> ProjectStep:
    return ProjectStep(
        project=project,
        name=step_in.name,
        planned_date=step_in.planned_date,
        weight=step_in.weight,
        progress=0,
        completion_date=None,
        comment=None,
        position=step_in.position,
        lock_version=1,
    )


def create_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    project_in: ProjectCreate,
) -> Project:
    category = _get_category(
        db,
        workspace_id=workspace_id,
        category_id=project_in.category_id,
        for_update=True,
    )
    project = Project(
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name=project_in.name,
        is_active=project_in.is_active,
        general_comment=None,
        last_tracking_saved_at=None,
        created_by_id=current_user.id,
        lock_version=1,
    )
    project.steps = [_new_step(project, step_in) for step_in in project_in.steps]
    if project.is_active:
        _validate_active_structure(project.steps)
    db.add(project)
    _flush(db)
    return project


def list_projects(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    is_active: bool | None = None,
    category_id: uuid.UUID | None = None,
    state: ProjectState | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
) -> tuple[list[Project], int]:
    filters = [Project.workspace_id == workspace_id]
    if is_active is not None:
        filters.append(Project.is_active == is_active)
    if category_id is not None:
        _get_category(db, workspace_id=workspace_id, category_id=category_id)
        filters.append(Project.category_id == category_id)

    planned_date = (
        select(func.max(ProjectStep.planned_date))
        .where(ProjectStep.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    step_count = (
        select(func.count(ProjectStep.id))
        .where(ProjectStep.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    minimum_progress = (
        select(func.min(ProjectStep.progress))
        .where(ProjectStep.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    maximum_progress = (
        select(func.max(ProjectStep.progress))
        .where(ProjectStep.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    complete_step_count = (
        select(func.count(ProjectStep.id))
        .where(
            ProjectStep.project_id == Project.id,
            ProjectStep.planned_date.is_not(None),
            ProjectStep.weight.is_not(None),
        )
        .correlate(Project)
        .scalar_subquery()
    )
    total_weight = (
        select(func.coalesce(func.sum(ProjectStep.weight), 0))
        .where(ProjectStep.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    if planned_from is not None:
        filters.append(planned_date >= planned_from)
    if planned_to is not None:
        filters.append(planned_date <= planned_to)
    complete_structure = (
        step_count > 0,
        complete_step_count == step_count,
        total_weight == Decimal("100.00"),
    )
    if state is ProjectState.NO_INICIADO:
        filters.extend((*complete_structure, maximum_progress == 0))
    elif state is ProjectState.FINALIZADO:
        filters.extend((*complete_structure, minimum_progress == 100))
    elif state is ProjectState.EN_PROCESO:
        filters.extend((*complete_structure, minimum_progress < 100, maximum_progress > 0))

    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    statement = (
        select(Project)
        .options(*_project_options())
        .where(*filters)
        .order_by(planned_date.asc().nulls_last(), Project.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), int(total)


def get_project(
    db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID
) -> Project:
    return _get_project(db, workspace_id=workspace_id, project_id=project_id)


def update_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_in: ProjectPlanningUpdate,
) -> Project:
    project = _get_project(
        db, workspace_id=workspace_id, project_id=project_id, for_update=True
    )
    if project.lock_version != project_in.lock_version:
        raise ProjectVersionConflictError("Project version is stale")
    changes = project_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    category: Category | None = None
    if "category_id" in changes and changes["category_id"] != project.category_id:
        category = _get_category(
            db,
            workspace_id=workspace_id,
            category_id=changes["category_id"],
            for_update=True,
        )
    if changes.get("is_active") is True and not project.is_active:
        _validate_active_structure(project.steps)
    result = db.execute(
        update(Project)
        .where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
            Project.lock_version == project_in.lock_version,
        )
        .values(**changes, lock_version=Project.lock_version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise ProjectVersionConflictError("Project version is stale")
    for field, value in changes.items():
        set_committed_value(project, field, value)
    if category is not None:
        set_committed_value(project, "category", category)
    set_committed_value(project, "lock_version", project_in.lock_version + 1)
    db.flush()
    return project


def create_project_step(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    step_in: ProjectStepCreate,
) -> ProjectStep:
    project = _get_project(
        db, workspace_id=workspace_id, project_id=project_id, for_update=True
    )
    if project.is_active:
        raise ProjectConflictError("Deactivate the Project before changing its Steps")
    if any(step.position == step_in.position for step in project.steps):
        raise ProjectConflictError("Project Step position already exists")
    step = _new_step(project, step_in)
    db.add(step)
    _flush(db)
    return step


def update_project_step(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    step_id: uuid.UUID,
    step_in: ProjectStepPlanningUpdate,
) -> ProjectStep:
    project = _get_project(
        db, workspace_id=workspace_id, project_id=project_id, for_update=True
    )
    if project.is_active:
        raise ProjectConflictError("Deactivate the Project before changing its Steps")
    step = next((row for row in project.steps if row.id == step_id), None)
    if step is None:
        raise ProjectStepNotFoundError("Project Step not found")
    if step.lock_version != step_in.lock_version:
        raise ProjectVersionConflictError("Project Step version is stale")
    changes = step_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    if "position" in changes and any(
        row.id != step.id and row.position == changes["position"] for row in project.steps
    ):
        raise ProjectConflictError("Project Step position already exists")
    try:
        result = db.execute(
            update(ProjectStep)
            .where(
                ProjectStep.id == step_id,
                ProjectStep.project_id == project_id,
                ProjectStep.lock_version == step_in.lock_version,
            )
            .values(**changes, lock_version=ProjectStep.lock_version + 1)
            .execution_options(synchronize_session=False)
        )
    except IntegrityError as error:
        if _constraint_name(error) == _STEP_POSITION_CONSTRAINT:
            raise ProjectConflictError("Project Step position already exists") from error
        raise
    if result.rowcount != 1:
        raise ProjectVersionConflictError("Project Step version is stale")
    for field, value in changes.items():
        set_committed_value(step, field, value)
    set_committed_value(step, "lock_version", step_in.lock_version + 1)
    db.flush()
    return step


def update_project_general_tracking(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_in: ProjectGeneralTrackingUpdate,
) -> Project:
    project = _get_project(db, workspace_id=workspace_id, project_id=project_id)
    if project.lock_version != project_in.lock_version:
        raise ProjectVersionConflictError("Project version is stale")
    changes = project_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    result = db.execute(
        update(Project)
        .where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
            Project.lock_version == project_in.lock_version,
        )
        .values(**changes, lock_version=Project.lock_version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise ProjectVersionConflictError("Project version is stale")
    for field, value in changes.items():
        set_committed_value(project, field, value)
    set_committed_value(project, "lock_version", project_in.lock_version + 1)
    db.flush()
    return project


def save_project_tracking(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    tracking_in: ProjectTrackingBatch,
    local_date: date,
    saved_at: datetime | None = None,
) -> tuple[Project, datetime]:
    project = _get_project(
        db, workspace_id=workspace_id, project_id=project_id, for_update=True
    )
    if not project.is_active:
        raise ProjectConflictError("Inactive Projects cannot be tracked")
    if project.lock_version != tracking_in.project_lock_version:
        raise ProjectVersionConflictError("Project version is stale")
    expected = {row.id: row for row in tracking_in.items}
    steps = list(
        db.scalars(
            select(ProjectStep)
            .where(
                ProjectStep.project_id == project_id,
                ProjectStep.id.in_(expected),
            )
            .order_by(ProjectStep.id)
            .with_for_update()
        ).all()
    )
    if len(steps) != len(expected):
        raise ProjectStepNotFoundError("One or more Project Steps were not found")
    if any(step.lock_version != expected[step.id].lock_version for step in steps):
        raise ProjectVersionConflictError("One or more Project Step versions are stale")

    for step in steps:
        row = expected[step.id]
        changes = row.model_dump(exclude_unset=True, exclude={"id", "lock_version"})
        if "progress" in changes:
            if changes["progress"] == 100 and step.progress < 100:
                changes["completion_date"] = local_date
            elif changes["progress"] < 100:
                changes["completion_date"] = None
        result = db.execute(
            update(ProjectStep)
            .where(
                ProjectStep.id == step.id,
                ProjectStep.project_id == project_id,
                ProjectStep.lock_version == row.lock_version,
            )
            .values(**changes, lock_version=ProjectStep.lock_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ProjectVersionConflictError(
                "One or more Project Step versions are stale"
            )
        for field, value in changes.items():
            set_committed_value(step, field, value)
        set_committed_value(step, "lock_version", row.lock_version + 1)

    timestamp = saved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("saved_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    result = db.execute(
        update(Project)
        .where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
            Project.lock_version == tracking_in.project_lock_version,
        )
        .values(
            last_tracking_saved_at=timestamp,
            lock_version=Project.lock_version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise ProjectVersionConflictError("Project version is stale")
    set_committed_value(project, "last_tracking_saved_at", timestamp)
    set_committed_value(project, "lock_version", tracking_in.project_lock_version + 1)
    db.flush()
    return project, timestamp


def list_review_eligible_project_steps(
    db: Session, *, workspace_id: uuid.UUID, local_date: date
) -> list[ProjectStep]:
    statement = (
        select(ProjectStep)
        .join(Project)
        .options(selectinload(ProjectStep.project))
        .where(
            Project.workspace_id == workspace_id,
            Project.is_active.is_(True),
            ProjectStep.progress < 100,
            ProjectStep.planned_date <= local_date,
        )
        .order_by(ProjectStep.planned_date, ProjectStep.project_id, ProjectStep.position)
    )
    return list(db.scalars(statement).all())
