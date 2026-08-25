import uuid

from collections.abc import Callable

from fastapi import APIRouter, Query, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency
from app.api.v2.errors import V2APIError
from app.models import ActivityMaster, Category, MasterTask
from app.schemas.v2_catalog import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemRead,
    CatalogItemUpdate,
    CatalogLifecycleUpdate,
    CategoryCreate,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdate,
)
from app.services.v2_catalog import (
    CatalogCategoryUnavailableError,
    CatalogNameConflictError,
    CatalogNotFoundError,
    CatalogVersionConflictError,
    create_category,
    create_item,
    get_category,
    get_item,
    list_categories,
    list_items,
    set_category_active,
    set_item_active,
    update_category,
    update_item,
)


router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["V2 Catalogs"])


def _error(error: ValueError) -> None:
    if isinstance(error, CatalogNotFoundError):
        raise V2APIError(status_code=404, code="CATALOG_NOT_FOUND", message="No se encontró el registro.") from error
    if isinstance(error, CatalogNameConflictError):
        raise V2APIError(status_code=409, code="CATALOG_NAME_CONFLICT", message="Ya existe un registro con ese nombre.") from error
    if isinstance(error, CatalogVersionConflictError):
        raise V2APIError(status_code=409, code="CATALOG_VERSION_CONFLICT", message="El registro cambió. Actualiza e inténtalo nuevamente.") from error
    raise V2APIError(status_code=409, code="CATEGORY_UNAVAILABLE", message="La categoría no está disponible.") from error


def _category_read(category: Category) -> CategoryRead:
    return CategoryRead.model_validate(category)


def _item_read(item: MasterTask | ActivityMaster) -> CatalogItemRead:
    return CatalogItemRead(
        id=item.id, workspace_id=item.workspace_id, category_id=item.category_id,
        name=item.name, category_name=item.category.name, is_active=item.is_active,
        lock_version=item.lock_version, created_at=item.created_at, updated_at=item.updated_at,
    )


def _write(operation: Callable[[], Category | MasterTask | ActivityMaster], db: SessionDependency):
    try:
        entity = operation()
        db.commit()
        db.refresh(entity)
        return entity
    except (CatalogNotFoundError, CatalogNameConflictError, CatalogVersionConflictError, CatalogCategoryUnavailableError) as error:
        db.rollback()
        _error(error)
    except Exception:
        db.rollback()
        raise


@router.get("/categories", response_model=CategoryListResponse)
def categories_index(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, active: bool | None = None, search: str | None = Query(default=None, max_length=100)) -> CategoryListResponse:
    del access
    items, total = list_categories(db, workspace_id=workspace_id, active=active, search=search)
    return CategoryListResponse(items=[_category_read(item) for item in items], total=total)


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def categories_create(workspace_id: uuid.UUID, category_in: CategoryCreate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    return _category_read(_write(lambda: create_category(db, workspace_id=workspace_id, category_in=category_in), db))


@router.get("/categories/{category_id}", response_model=CategoryRead)
def categories_get(workspace_id: uuid.UUID, category_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    try:
        return _category_read(get_category(db, workspace_id=workspace_id, category_id=category_id))
    except CatalogNotFoundError as error:
        _error(error)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def categories_update(workspace_id: uuid.UUID, category_id: uuid.UUID, category_in: CategoryUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    return _category_read(_write(lambda: update_category(db, workspace_id=workspace_id, category_id=category_id, category_in=category_in), db))


def _category_lifecycle(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership, *, active: bool) -> CategoryRead:
    del access
    return _category_read(_write(lambda: set_category_active(db, workspace_id=workspace_id, category_id=category_id, expected_version=lifecycle_in.lock_version, active=active), db))


@router.post("/categories/{category_id}/activate", response_model=CategoryRead)
def categories_activate(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    return _category_lifecycle(workspace_id, category_id, lifecycle_in, db, access, active=True)


@router.post("/categories/{category_id}/deactivate", response_model=CategoryRead)
def categories_deactivate(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    return _category_lifecycle(workspace_id, category_id, lifecycle_in, db, access, active=False)


def _item_routes(path: str, model: type[MasterTask] | type[ActivityMaster]) -> APIRouter:
    child = APIRouter(prefix=f"/{path}")

    @child.get("", response_model=CatalogItemListResponse)
    def index(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, active: bool | None = None, category_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=150)) -> CatalogItemListResponse:
        del access
        try:
            items, total = list_items(db, model=model, workspace_id=workspace_id, active=active, category_id=category_id, search=search)
        except CatalogNotFoundError as error:
            _error(error)
        return CatalogItemListResponse(items=[_item_read(item) for item in items], total=total)

    @child.post("", response_model=CatalogItemRead, status_code=status.HTTP_201_CREATED)
    def create(workspace_id: uuid.UUID, item_in: CatalogItemCreate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        return _item_read(_write(lambda: create_item(db, model=model, workspace_id=workspace_id, item_in=item_in), db))

    @child.get("/{item_id}", response_model=CatalogItemRead)
    def get(workspace_id: uuid.UUID, item_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        try:
            return _item_read(get_item(db, model=model, workspace_id=workspace_id, item_id=item_id))
        except CatalogNotFoundError as error:
            _error(error)

    @child.patch("/{item_id}", response_model=CatalogItemRead)
    def patch(workspace_id: uuid.UUID, item_id: uuid.UUID, item_in: CatalogItemUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        return _item_read(_write(lambda: update_item(db, model=model, workspace_id=workspace_id, item_id=item_id, item_in=item_in), db))

    def lifecycle(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership, *, active: bool) -> CatalogItemRead:
        del access
        return _item_read(_write(lambda: set_item_active(db, model=model, workspace_id=workspace_id, item_id=item_id, expected_version=lifecycle_in.lock_version, active=active), db))

    @child.post("/{item_id}/activate", response_model=CatalogItemRead)
    def activate(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        return lifecycle(workspace_id, item_id, lifecycle_in, db, access, active=True)

    @child.post("/{item_id}/deactivate", response_model=CatalogItemRead)
    def deactivate(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        return lifecycle(workspace_id, item_id, lifecycle_in, db, access, active=False)

    return child


router.include_router(_item_routes("master-tasks", MasterTask))
router.include_router(_item_routes("activity-masters", ActivityMaster))
