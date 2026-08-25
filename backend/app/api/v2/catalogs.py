import uuid

from collections.abc import Callable

from fastapi import APIRouter, Query, Response, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency
from app.api.v2.errors import V2APIError
from app.models import ActivityMaster, Category, MasterTask
from app.schemas.v2_catalog import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemRead,
    CatalogItemUpdate,
    CatalogLifecycleUpdate,
    CatalogSelectorOption,
    CategoryCreate,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdate,
)
from app.services.v2_catalog import (
    CatalogCategoryUnavailableError,
    CatalogNameConflictError,
    CatalogNotFoundError,
    CatalogReferencedError,
    CatalogVersionConflictError,
    can_delete_category,
    can_delete_item,
    category_selector,
    create_category,
    create_item,
    delete_category,
    delete_item,
    get_category,
    get_item,
    list_categories,
    list_items,
    item_selector,
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
    if isinstance(error, CatalogReferencedError):
        raise V2APIError(status_code=409, code="CATALOG_REFERENCED", message="El registro está en uso y no puede eliminarse.") from error
    raise V2APIError(status_code=409, code="CATEGORY_UNAVAILABLE", message="La categoría no está disponible.") from error


def _category_read(db: SessionDependency, category: Category) -> CategoryRead:
    return CategoryRead(
        id=category.id,
        workspace_id=category.workspace_id,
        name=category.name,
        is_active=category.is_active,
        lock_version=category.lock_version,
        can_delete=can_delete_category(db, workspace_id=category.workspace_id, category_id=category.id),
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _item_read(db: SessionDependency, item: MasterTask | ActivityMaster) -> CatalogItemRead:
    return CatalogItemRead(
        id=item.id, workspace_id=item.workspace_id, category_id=item.category_id,
        name=item.name, category_name=item.category.name, is_active=item.is_active,
        lock_version=item.lock_version, created_at=item.created_at, updated_at=item.updated_at,
        can_delete=can_delete_item(db, model=type(item), workspace_id=item.workspace_id, item_id=item.id),
    )


def _write(operation: Callable[[], Category | MasterTask | ActivityMaster], db: SessionDependency):
    try:
        entity = operation()
        db.commit()
        db.refresh(entity)
        return entity
    except (CatalogNotFoundError, CatalogNameConflictError, CatalogVersionConflictError, CatalogCategoryUnavailableError, CatalogReferencedError) as error:
        db.rollback()
        _error(error)
    except Exception:
        db.rollback()
        raise


@router.get("/categories", response_model=CategoryListResponse)
def categories_index(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, active: bool | None = None, search: str | None = Query(default=None, max_length=100)) -> CategoryListResponse:
    del access
    items, total = list_categories(db, workspace_id=workspace_id, active=active, search=search)
    return CategoryListResponse(items=[_category_read(db, item) for item in items], total=total)


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def categories_create(workspace_id: uuid.UUID, category_in: CategoryCreate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    return _category_read(db, _write(lambda: create_category(db, workspace_id=workspace_id, category_in=category_in), db))


@router.get("/categories/{category_id}", response_model=CategoryRead)
def categories_get(workspace_id: uuid.UUID, category_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    try:
        return _category_read(db, get_category(db, workspace_id=workspace_id, category_id=category_id))
    except CatalogNotFoundError as error:
        _error(error)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def categories_update(workspace_id: uuid.UUID, category_id: uuid.UUID, category_in: CategoryUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    del access
    return _category_read(db, _write(lambda: update_category(db, workspace_id=workspace_id, category_id=category_id, category_in=category_in), db))


def _category_lifecycle(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership, *, active: bool) -> CategoryRead:
    del access
    return _category_read(db, _write(lambda: set_category_active(db, workspace_id=workspace_id, category_id=category_id, expected_version=lifecycle_in.lock_version, active=active), db))


@router.post("/categories/{category_id}/activate", response_model=CategoryRead)
def categories_activate(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    return _category_lifecycle(workspace_id, category_id, lifecycle_in, db, access, active=True)


@router.post("/categories/{category_id}/deactivate", response_model=CategoryRead)
def categories_deactivate(workspace_id: uuid.UUID, category_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CategoryRead:
    return _category_lifecycle(workspace_id, category_id, lifecycle_in, db, access, active=False)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def categories_delete(workspace_id: uuid.UUID, category_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, lock_version: int = Query(ge=1)) -> Response:
    del access
    try:
        delete_category(db, workspace_id=workspace_id, category_id=category_id, expected_version=lock_version)
        db.commit()
    except (CatalogNotFoundError, CatalogVersionConflictError, CatalogReferencedError) as error:
        db.rollback()
        _error(error)
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _item_routes(path: str, model: type[MasterTask] | type[ActivityMaster]) -> APIRouter:
    child = APIRouter(prefix=f"/{path}")

    @child.get("", response_model=CatalogItemListResponse)
    def index(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, active: bool | None = None, category_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=150)) -> CatalogItemListResponse:
        del access
        try:
            items, total = list_items(db, model=model, workspace_id=workspace_id, active=active, category_id=category_id, search=search)
        except CatalogNotFoundError as error:
            _error(error)
        return CatalogItemListResponse(items=[_item_read(db, item) for item in items], total=total)

    @child.post("", response_model=CatalogItemRead, status_code=status.HTTP_201_CREATED)
    def create(workspace_id: uuid.UUID, item_in: CatalogItemCreate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        return _item_read(db, _write(lambda: create_item(db, model=model, workspace_id=workspace_id, item_in=item_in), db))

    @child.get("/{item_id}", response_model=CatalogItemRead)
    def get(workspace_id: uuid.UUID, item_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        try:
            return _item_read(db, get_item(db, model=model, workspace_id=workspace_id, item_id=item_id))
        except CatalogNotFoundError as error:
            _error(error)

    @child.patch("/{item_id}", response_model=CatalogItemRead)
    def patch(workspace_id: uuid.UUID, item_id: uuid.UUID, item_in: CatalogItemUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        del access
        return _item_read(db, _write(lambda: update_item(db, model=model, workspace_id=workspace_id, item_id=item_id, item_in=item_in), db))

    def lifecycle(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership, *, active: bool) -> CatalogItemRead:
        del access
        return _item_read(db, _write(lambda: set_item_active(db, model=model, workspace_id=workspace_id, item_id=item_id, expected_version=lifecycle_in.lock_version, active=active), db))

    @child.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(workspace_id: uuid.UUID, item_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, lock_version: int = Query(ge=1)) -> Response:
        del access
        try:
            delete_item(db, model=model, workspace_id=workspace_id, item_id=item_id, expected_version=lock_version)
            db.commit()
        except (CatalogNotFoundError, CatalogVersionConflictError, CatalogReferencedError) as error:
            db.rollback()
            _error(error)
        except Exception:
            db.rollback()
            raise
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @child.post("/{item_id}/activate", response_model=CatalogItemRead)
    def activate(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        return lifecycle(workspace_id, item_id, lifecycle_in, db, access, active=True)

    @child.post("/{item_id}/deactivate", response_model=CatalogItemRead)
    def deactivate(workspace_id: uuid.UUID, item_id: uuid.UUID, lifecycle_in: CatalogLifecycleUpdate, db: SessionDependency, access: ActiveWorkspaceMembership) -> CatalogItemRead:
        return lifecycle(workspace_id, item_id, lifecycle_in, db, access, active=False)

    return child


router.include_router(_item_routes("master-tasks", MasterTask))
router.include_router(_item_routes("activity-masters", ActivityMaster))


@router.get("/selectors/categories", response_model=list[CatalogSelectorOption])
def category_options(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, current_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=100)) -> list[CatalogSelectorOption]:
    del access
    return [CatalogSelectorOption(id=item.id, name=item.name, is_active=item.is_active) for item in category_selector(db, workspace_id=workspace_id, current_id=current_id, search=search)]


def _selector_options(db: SessionDependency, *, model, workspace_id: uuid.UUID, current_id: uuid.UUID | None, search: str | None) -> list[CatalogSelectorOption]:
    return [CatalogSelectorOption(id=item.id, name=item.name, is_active=item.is_active, category_id=item.category_id, category_name=item.category.name) for item in item_selector(db, model=model, workspace_id=workspace_id, current_id=current_id, search=search)]


@router.get("/selectors/tasks", response_model=list[CatalogSelectorOption])
def task_options(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, current_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=150)) -> list[CatalogSelectorOption]:
    del access
    return _selector_options(db, model=MasterTask, workspace_id=workspace_id, current_id=current_id, search=search)


@router.get("/selectors/activities", response_model=list[CatalogSelectorOption])
def activity_options(workspace_id: uuid.UUID, db: SessionDependency, access: ActiveWorkspaceMembership, current_id: uuid.UUID | None = None, search: str | None = Query(default=None, max_length=150)) -> list[CatalogSelectorOption]:
    del access
    return _selector_options(db, model=ActivityMaster, workspace_id=workspace_id, current_id=current_id, search=search)
