import uuid

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, SessionDependency
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import category_service


router = APIRouter(
    prefix="/workspaces/{workspace_id}/categories",
    tags=["Categories"],
)


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, category_service.CategoryNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        ) from error
    if isinstance(error, category_service.CategoryNameConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(error),
    ) from error


def _commit_category_write(
    db: Session,
    operation: Callable[..., Category],
    **kwargs: object,
) -> CategoryRead:
    try:
        category = operation(db, **kwargs)
        db.commit()
        db.refresh(category)
    except (
        category_service.CategoryNotFoundError,
        category_service.CategoryPermissionError,
        category_service.CategoryNameConflictError,
    ) as error:
        db.rollback()
        _raise_http_error(error)
    except Exception:
        db.rollback()
        raise
    return CategoryRead.model_validate(category)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    workspace_id: uuid.UUID,
    category_in: CategoryCreate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> CategoryRead:
    return _commit_category_write(
        db,
        category_service.create_category,
        workspace_id=workspace_id,
        current_user=current_user,
        category_in=category_in,
    )


@router.get("", response_model=list[CategoryRead])
def list_categories(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    active: bool | None = Query(default=None),
) -> list[CategoryRead]:
    try:
        categories = category_service.list_categories(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
            active=active,
        )
    except category_service.CategoryPermissionError as error:
        _raise_http_error(error)
    return [CategoryRead.model_validate(category) for category in categories]


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> CategoryRead:
    try:
        category = category_service.get_category(
            db,
            workspace_id=workspace_id,
            category_id=category_id,
            current_user=current_user,
        )
    except (
        category_service.CategoryNotFoundError,
        category_service.CategoryPermissionError,
    ) as error:
        _raise_http_error(error)
    return CategoryRead.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> CategoryRead:
    return _commit_category_write(
        db,
        category_service.update_category,
        workspace_id=workspace_id,
        category_id=category_id,
        current_user=current_user,
        category_in=category_in,
    )


@router.post("/{category_id}/activate", response_model=CategoryRead)
def activate_category(
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> CategoryRead:
    return _commit_category_write(
        db,
        category_service.activate_category,
        workspace_id=workspace_id,
        category_id=category_id,
        current_user=current_user,
    )


@router.post("/{category_id}/deactivate", response_model=CategoryRead)
def deactivate_category(
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
) -> CategoryRead:
    return _commit_category_write(
        db,
        category_service.deactivate_category,
        workspace_id=workspace_id,
        category_id=category_id,
        current_user=current_user,
    )
