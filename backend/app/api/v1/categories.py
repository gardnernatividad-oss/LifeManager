import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import PersonalWorkspace, SessionDependency
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdate,
)
from app.services import category_service


router = APIRouter(prefix="/categories", tags=["Categories"])


def _category_error(error: Exception) -> HTTPException:
    if isinstance(error, category_service.CategoryNotFoundError):
        return HTTPException(status_code=404, detail="Category not found")
    if isinstance(error, category_service.CategoryNameConflictError):
        return HTTPException(status_code=409, detail="Category name already exists")
    if isinstance(error, category_service.CategoryInUseError):
        return HTTPException(status_code=409, detail="Category is already in use")
    raise error


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> CategoryRead:
    try:
        category = category_service.create_category(
            db, workspace_id=workspace.id, category_in=category_in
        )
        db.commit()
        db.refresh(category)
    except (
        category_service.CategoryNameConflictError,
        category_service.CategoryInUseError,
    ) as error:
        db.rollback()
        raise _category_error(error) from error
    except Exception:
        db.rollback()
        raise
    return CategoryRead.model_validate(category)


@router.get("", response_model=CategoryListResponse)
def list_categories(
    db: SessionDependency,
    workspace: PersonalWorkspace,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> CategoryListResponse:
    items, total = category_service.list_categories(
        db,
        workspace_id=workspace.id,
        page=page,
        page_size=page_size,
    )
    return CategoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> CategoryRead:
    try:
        category = category_service.update_category(
            db,
            workspace_id=workspace.id,
            category_id=category_id,
            category_in=category_in,
        )
        db.commit()
        db.refresh(category)
    except (
        category_service.CategoryNotFoundError,
        category_service.CategoryNameConflictError,
        category_service.CategoryInUseError,
    ) as error:
        db.rollback()
        raise _category_error(error) from error
    except Exception:
        db.rollback()
        raise
    return CategoryRead.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: SessionDependency,
    workspace: PersonalWorkspace,
) -> Response:
    try:
        category_service.delete_category(
            db, workspace_id=workspace.id, category_id=category_id
        )
        db.commit()
    except (
        category_service.CategoryNotFoundError,
        category_service.CategoryInUseError,
    ) as error:
        db.rollback()
        raise _category_error(error) from error
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
