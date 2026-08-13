import uuid

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.pending_item import (
    PendingItemCompliance,
    PendingItemCreate,
    PendingItemListResponse,
    PendingItemPlanningUpdate,
    PendingItemRead,
    PendingItemState,
    PendingItemTrackingBatch,
    PendingItemTrackingBatchResponse,
)
from app.services import pending_item_service


router = APIRouter(prefix="/pending-items", tags=["Pending Items"])

_DOMAIN_ERRORS = (
    pending_item_service.PendingItemNotFoundError,
    pending_item_service.PendingItemCategoryNotFoundError,
    pending_item_service.PendingItemConflictError,
    pending_item_service.PendingItemVersionConflictError,
)


def _error(error: Exception) -> HTTPException:
    if isinstance(
        error,
        (
            pending_item_service.PendingItemNotFoundError,
            pending_item_service.PendingItemCategoryNotFoundError,
        ),
    ):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


def _today(current_user: CurrentUser) -> date:
    return local_today(current_user.timezone)


@router.post("", response_model=PendingItemRead, status_code=status.HTTP_201_CREATED)
def create_pending_item(
    item_in: PendingItemCreate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> PendingItemRead:
    today = _today(current_user)
    try:
        item = pending_item_service.create_pending_item(
            db,
            workspace_id=workspace.id,
            current_user=current_user,
            item_in=item_in,
        )
        db.commit()
        db.refresh(item)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return PendingItemRead.from_pending_item(item, local_date=today)


@router.get("", response_model=PendingItemListResponse)
def list_pending_items(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    is_active: bool | None = None,
    unfinished: bool | None = None,
    category_id: uuid.UUID | None = None,
    state: PendingItemState | None = None,
    compliance: PendingItemCompliance | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
) -> PendingItemListResponse:
    today = _today(current_user)
    try:
        items, total = pending_item_service.list_pending_items(
            db,
            workspace_id=workspace.id,
            local_date=today,
            page=page,
            page_size=page_size,
            is_active=is_active,
            unfinished=unfinished,
            category_id=category_id,
            state=state,
            compliance=compliance,
            planned_from=planned_from,
            planned_to=planned_to,
        )
    except _DOMAIN_ERRORS as error:
        raise _error(error) from error
    return PendingItemListResponse(
        items=[PendingItemRead.from_pending_item(item, local_date=today) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.patch("/tracking", response_model=PendingItemTrackingBatchResponse)
def save_tracking(
    tracking_in: PendingItemTrackingBatch,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> PendingItemTrackingBatchResponse:
    today = _today(current_user)
    try:
        items, saved_at = pending_item_service.save_pending_item_tracking(
            db,
            workspace_id=workspace.id,
            tracking_in=tracking_in,
            local_date=today,
        )
        db.commit()
        for item in items:
            db.refresh(item)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return PendingItemTrackingBatchResponse(
        items=[PendingItemRead.from_pending_item(item, local_date=today) for item in items],
        saved_at=saved_at,
    )


@router.get("/{pending_item_id}", response_model=PendingItemRead)
def get_pending_item(
    pending_item_id: uuid.UUID,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> PendingItemRead:
    try:
        item = pending_item_service.get_pending_item(
            db, workspace_id=workspace.id, pending_item_id=pending_item_id
        )
    except _DOMAIN_ERRORS as error:
        raise _error(error) from error
    return PendingItemRead.from_pending_item(item, local_date=_today(current_user))


@router.patch("/{pending_item_id}", response_model=PendingItemRead)
def update_pending_item(
    pending_item_id: uuid.UUID,
    item_in: PendingItemPlanningUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> PendingItemRead:
    today = _today(current_user)
    try:
        item = pending_item_service.update_pending_item(
            db,
            workspace_id=workspace.id,
            pending_item_id=pending_item_id,
            item_in=item_in,
        )
        db.commit()
        db.refresh(item)
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return PendingItemRead.from_pending_item(item, local_date=today)
