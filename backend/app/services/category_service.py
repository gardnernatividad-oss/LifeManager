import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.names import normalize_name
from app.models import Category, MasterTask, PendingItem, Project
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryNotFoundError(LookupError):
    pass


class CategoryNameConflictError(ValueError):
    pass


class CategoryInUseError(ValueError):
    pass


_CATEGORY_UNIQUE_CONSTRAINT = "uq_categories_workspace_id_normalized_name"
_CATEGORY_REFERENCE_CONSTRAINTS = {
    "fk_master_tasks_category_workspace",
    "fk_pending_items_category_workspace",
    "fk_projects_category_workspace",
}


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint_name = _constraint_name(error)
        if constraint_name == _CATEGORY_UNIQUE_CONSTRAINT:
            raise CategoryNameConflictError("Category name already exists") from error
        if constraint_name in _CATEGORY_REFERENCE_CONSTRAINTS:
            raise CategoryInUseError("Category is already in use") from error
        raise


def _get_category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.workspace_id == workspace_id,
        )
    )
    if category is None:
        raise CategoryNotFoundError("Category not found")
    return category


def _name_exists(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    normalized_name: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    statement = select(Category.id).where(
        Category.workspace_id == workspace_id,
        Category.normalized_name == normalized_name,
    )
    if exclude_id is not None:
        statement = statement.where(Category.id != exclude_id)
    return db.scalar(statement) is not None


def _is_used(db: Session, *, category_id: uuid.UUID) -> bool:
    statement = select(
        or_(
            exists().where(MasterTask.category_id == category_id),
            exists().where(PendingItem.category_id == category_id),
            exists().where(Project.category_id == category_id),
        )
    )
    return bool(db.scalar(statement))


def create_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_in: CategoryCreate,
) -> Category:
    name, normalized_name = normalize_name(
        category_in.name, max_length=100, field_label="Category"
    )
    if _name_exists(db, workspace_id=workspace_id, normalized_name=normalized_name):
        raise CategoryNameConflictError("Category name already exists")
    category = Category(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalized_name,
    )
    db.add(category)
    _flush(db)
    return category


def list_categories(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Category], int]:
    filters = (Category.workspace_id == workspace_id,)
    total = db.scalar(select(func.count()).select_from(Category).where(*filters)) or 0
    statement = (
        select(Category)
        .where(*filters)
        .order_by(Category.normalized_name, Category.name, Category.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), total


def update_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
) -> Category:
    category = _get_category(db, workspace_id=workspace_id, category_id=category_id)
    changes = category_in.model_dump(exclude_unset=True)
    if not changes:
        return category
    if _is_used(db, category_id=category.id):
        raise CategoryInUseError("Category is already in use")
    name, normalized_name = normalize_name(
        changes["name"], max_length=100, field_label="Category"
    )
    if normalized_name != category.normalized_name and _name_exists(
        db,
        workspace_id=workspace_id,
        normalized_name=normalized_name,
        exclude_id=category.id,
    ):
        raise CategoryNameConflictError("Category name already exists")
    category.name = name
    category.normalized_name = normalized_name
    _flush(db)
    return category


def delete_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
) -> None:
    category = _get_category(db, workspace_id=workspace_id, category_id=category_id)
    if _is_used(db, category_id=category.id):
        raise CategoryInUseError("Category is already in use")
    db.delete(category)
    _flush(db)
