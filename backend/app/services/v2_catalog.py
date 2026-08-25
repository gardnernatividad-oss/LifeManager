import uuid

from typing import TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.names import normalize_name
from app.models import ActivityMaster, Category, MasterTask
from app.schemas.v2_catalog import CategoryCreate, CategoryUpdate, CatalogItemCreate, CatalogItemUpdate


class CatalogNotFoundError(LookupError):
    pass


class CatalogNameConflictError(ValueError):
    pass


class CatalogVersionConflictError(ValueError):
    pass


class CatalogCategoryUnavailableError(ValueError):
    pass


CatalogItem = TypeVar("CatalogItem", MasterTask, ActivityMaster)


def _integrity(error: IntegrityError) -> None:
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
    if constraint in {
        "uq_categories_workspace_normalized_name",
        "uq_master_tasks_workspace_normalized_name",
        "uq_activity_masters_workspace_normalized_name",
    }:
        raise CatalogNameConflictError("Catalog name already exists") from error
    if constraint == "fk_master_tasks_category_workspace" or constraint == "fk_activity_masters_category_workspace":
        raise CatalogCategoryUnavailableError("Category unavailable") from error
    raise error


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        _integrity(error)


def _execute_mutation(db: Session, statement):
    try:
        return db.execute(statement)
    except IntegrityError as error:
        _integrity(error)


def _category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, assignable: bool = False) -> Category:
    statement = select(Category).where(Category.id == category_id, Category.workspace_id == workspace_id)
    if assignable:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None:
        raise CatalogNotFoundError("Catalog item not found")
    if assignable and not category.is_active:
        raise CatalogCategoryUnavailableError("Category unavailable")
    return category


def create_category(db: Session, *, workspace_id: uuid.UUID, category_in: CategoryCreate) -> Category:
    name, normalized = normalize_name(category_in.name, max_length=100, field_label="Category")
    category = Category(workspace_id=workspace_id, name=name, normalized_name=normalized)
    db.add(category)
    _flush(db)
    return category


def list_categories(db: Session, *, workspace_id: uuid.UUID, active: bool | None = None, search: str | None = None) -> tuple[list[Category], int]:
    filters = [Category.workspace_id == workspace_id]
    if active is not None:
        filters.append(Category.is_active.is_(active))
    if search and search.strip():
        _, normalized = normalize_name(search, max_length=100, field_label="Search")
        filters.append(Category.normalized_name.contains(normalized, autoescape=True))
    total = db.scalar(select(func.count()).select_from(Category).where(*filters)) or 0
    items = list(db.scalars(select(Category).where(*filters).order_by(Category.normalized_name, Category.id)).all())
    return items, total


def get_category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    return _category(db, workspace_id=workspace_id, category_id=category_id)


def update_category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, category_in: CategoryUpdate) -> Category:
    values: dict[str, object] = {"lock_version": Category.lock_version + 1}
    if category_in.name is not None:
        values["name"], values["normalized_name"] = normalize_name(category_in.name, max_length=100, field_label="Category")
    result = _execute_mutation(db, update(Category).where(Category.id == category_id, Category.workspace_id == workspace_id, Category.lock_version == category_in.lock_version).values(**values).returning(Category.id))
    if result.scalar_one_or_none() is None:
        if db.scalar(select(Category.id).where(Category.id == category_id, Category.workspace_id == workspace_id)) is None:
            raise CatalogNotFoundError("Catalog item not found")
        raise CatalogVersionConflictError("Catalog version conflict")
    _flush(db)
    return _category(db, workspace_id=workspace_id, category_id=category_id)


def set_category_active(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID, expected_version: int, active: bool) -> Category:
    result = _execute_mutation(db, update(Category).where(Category.id == category_id, Category.workspace_id == workspace_id, Category.lock_version == expected_version).values(is_active=active, lock_version=Category.lock_version + 1).returning(Category.id))
    if result.scalar_one_or_none() is None:
        if db.scalar(select(Category.id).where(Category.id == category_id, Category.workspace_id == workspace_id)) is None:
            raise CatalogNotFoundError("Catalog item not found")
        raise CatalogVersionConflictError("Catalog version conflict")
    _flush(db)
    return _category(db, workspace_id=workspace_id, category_id=category_id)


def create_item(db: Session, *, model: type[CatalogItem], workspace_id: uuid.UUID, item_in: CatalogItemCreate) -> CatalogItem:
    _category(db, workspace_id=workspace_id, category_id=item_in.category_id, assignable=True)
    name, normalized = normalize_name(item_in.name, max_length=150, field_label="Catalog item")
    item = model(workspace_id=workspace_id, category_id=item_in.category_id, name=name, normalized_name=normalized)
    db.add(item)
    _flush(db)
    return item


def list_items(db: Session, *, model: type[CatalogItem], workspace_id: uuid.UUID, active: bool | None = None, category_id: uuid.UUID | None = None, search: str | None = None) -> tuple[list[CatalogItem], int]:
    filters = [model.workspace_id == workspace_id]
    if active is not None:
        filters.append(model.is_active.is_(active))
    if category_id is not None:
        _category(db, workspace_id=workspace_id, category_id=category_id)
        filters.append(model.category_id == category_id)
    if search and search.strip():
        _, normalized = normalize_name(search, max_length=150, field_label="Search")
        filters.append(model.normalized_name.contains(normalized, autoescape=True))
    total = db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    items = list(db.scalars(select(model).options(selectinload(model.category)).where(*filters).order_by(model.normalized_name, model.id)).all())
    return items, total


def get_item(db: Session, *, model: type[CatalogItem], workspace_id: uuid.UUID, item_id: uuid.UUID) -> CatalogItem:
    item = db.scalar(select(model).options(selectinload(model.category)).where(model.id == item_id, model.workspace_id == workspace_id))
    if item is None:
        raise CatalogNotFoundError("Catalog item not found")
    return item


def update_item(db: Session, *, model: type[CatalogItem], workspace_id: uuid.UUID, item_id: uuid.UUID, item_in: CatalogItemUpdate) -> CatalogItem:
    values: dict[str, object] = {"lock_version": model.lock_version + 1}
    if item_in.name is not None:
        values["name"], values["normalized_name"] = normalize_name(item_in.name, max_length=150, field_label="Catalog item")
    if item_in.category_id is not None:
        _category(db, workspace_id=workspace_id, category_id=item_in.category_id, assignable=True)
        values["category_id"] = item_in.category_id
    result = _execute_mutation(db, update(model).where(model.id == item_id, model.workspace_id == workspace_id, model.lock_version == item_in.lock_version).values(**values).returning(model.id))
    if result.scalar_one_or_none() is None:
        if db.scalar(select(model.id).where(model.id == item_id, model.workspace_id == workspace_id)) is None:
            raise CatalogNotFoundError("Catalog item not found")
        raise CatalogVersionConflictError("Catalog version conflict")
    _flush(db)
    return get_item(db, model=model, workspace_id=workspace_id, item_id=item_id)


def set_item_active(db: Session, *, model: type[CatalogItem], workspace_id: uuid.UUID, item_id: uuid.UUID, expected_version: int, active: bool) -> CatalogItem:
    result = _execute_mutation(db, update(model).where(model.id == item_id, model.workspace_id == workspace_id, model.lock_version == expected_version).values(is_active=active, lock_version=model.lock_version + 1).returning(model.id))
    if result.scalar_one_or_none() is None:
        if db.scalar(select(model.id).where(model.id == item_id, model.workspace_id == workspace_id)) is None:
            raise CatalogNotFoundError("Catalog item not found")
        raise CatalogVersionConflictError("Catalog version conflict")
    _flush(db)
    return get_item(db, model=model, workspace_id=workspace_id, item_id=item_id)
