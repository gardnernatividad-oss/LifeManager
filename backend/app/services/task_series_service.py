import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.project import Project
from app.models.task_series import TaskSeries
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.task_series import TaskSeriesCreate, TaskSeriesUpdate, validate_recurrence_state
from app.services.workspace import get_workspace_membership


class TaskSeriesNotFoundError(LookupError): pass
class TaskSeriesPermissionError(PermissionError): pass
class TaskSeriesCategoryNotFoundError(LookupError): pass
class TaskSeriesCategoryInactiveError(ValueError): pass
class TaskSeriesProjectNotFoundError(LookupError): pass
class TaskSeriesProjectInactiveError(ValueError): pass
class TaskSeriesRecurrenceValidationError(ValueError): pass


def _require_membership(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
    membership = get_workspace_membership(db, workspace_id=workspace_id, user_id=user_id)
    if membership is None:
        raise TaskSeriesPermissionError("Workspace access denied")
    return membership


def _get_scoped(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID) -> TaskSeries:
    series = db.scalar(select(TaskSeries).where(TaskSeries.id == series_id, TaskSeries.workspace_id == workspace_id))
    if series is None:
        raise TaskSeriesNotFoundError("Task series not found")
    return series


def _resolve_category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, require_active: bool) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.workspace_id == workspace_id))
    if category is None:
        raise TaskSeriesCategoryNotFoundError("Category not found")
    if require_active and not category.is_active:
        raise TaskSeriesCategoryInactiveError("Category is inactive")
    return category


def _resolve_project(db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, require_active: bool) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id))
    if project is None:
        raise TaskSeriesProjectNotFoundError("Project not found")
    if require_active and not project.is_active:
        raise TaskSeriesProjectInactiveError("Project is inactive")
    return project


def _validate(values: dict[str, object]) -> None:
    try:
        validate_recurrence_state(
            frequency=values["frequency"],
            weekdays=values["weekdays"],
            month_day=values["month_day"],
            starts_at=values["starts_at"],
            ends_at=values["ends_at"],
        )
    except ValueError as error:
        raise TaskSeriesRecurrenceValidationError(str(error)) from error


def create_task_series(db: Session, *, workspace_id: uuid.UUID, current_user: User, series_in: TaskSeriesCreate) -> TaskSeries:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    data = series_in.model_dump()
    category_id = data.pop("category_id"); project_id = data.pop("project_id")
    _validate(data)
    if category_id is not None:
        _resolve_category(db, workspace_id=workspace_id, category_id=category_id, require_active=True)
    if project_id is not None:
        _resolve_project(db, workspace_id=workspace_id, project_id=project_id, require_active=True)
    series = TaskSeries(workspace_id=workspace_id, created_by_id=current_user.id, category_id=category_id, project_id=project_id, is_active=True, **data)
    db.add(series); db.flush(); return series


def list_task_series(db: Session, *, workspace_id: uuid.UUID, current_user: User, is_active: bool | None = None, category_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None) -> tuple[list[TaskSeries], int]:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    filters: list[object] = [TaskSeries.workspace_id == workspace_id]
    if is_active is not None: filters.append(TaskSeries.is_active.is_(is_active))
    if category_id is not None:
        _resolve_category(db, workspace_id=workspace_id, category_id=category_id, require_active=False)
        filters.append(TaskSeries.category_id == category_id)
    if project_id is not None:
        _resolve_project(db, workspace_id=workspace_id, project_id=project_id, require_active=False)
        filters.append(TaskSeries.project_id == project_id)
    statement = select(TaskSeries).where(*filters).order_by(TaskSeries.is_active.desc(), TaskSeries.title, TaskSeries.created_at, TaskSeries.id)
    items = list(db.scalars(statement).all())
    total = db.scalar(select(func.count()).select_from(TaskSeries).where(*filters))
    return items, int(total or 0)


def get_task_series(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID, current_user: User) -> TaskSeries:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    return _get_scoped(db, workspace_id=workspace_id, series_id=series_id)


def update_task_series(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID, current_user: User, series_in: TaskSeriesUpdate) -> TaskSeries:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    series = _get_scoped(db, workspace_id=workspace_id, series_id=series_id)
    changes = series_in.model_dump(exclude_unset=True)
    merged = {key: changes.get(key, getattr(series, key)) for key in ("frequency", "weekdays", "month_day", "starts_at", "ends_at")}
    _validate(merged)
    for association, resolver in (("category_id", _resolve_category), ("project_id", _resolve_project)):
        if association in changes and changes[association] is not None:
            resolver(db, workspace_id=workspace_id, **{association: changes[association]}, require_active=True)
    for field, value in changes.items(): setattr(series, field, value)
    db.flush(); return series


def activate_task_series(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID, current_user: User) -> TaskSeries:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    series = _get_scoped(db, workspace_id=workspace_id, series_id=series_id)
    _validate({key: getattr(series, key) for key in ("frequency", "weekdays", "month_day", "starts_at", "ends_at")})
    if not series.is_active: series.is_active = True; db.flush()
    return series


def deactivate_task_series(db: Session, *, workspace_id: uuid.UUID, series_id: uuid.UUID, current_user: User) -> TaskSeries:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    series = _get_scoped(db, workspace_id=workspace_id, series_id=series_id)
    if series.is_active: series.is_active = False; db.flush()
    return series
