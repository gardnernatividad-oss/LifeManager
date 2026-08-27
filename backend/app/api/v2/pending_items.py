import math
import uuid

from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.models import PendingItem, User
from app.schemas.v2_pending_item import PendingItemCompliance, PendingItemCorrection, PendingItemCreate, PendingItemHistoryListResponse, PendingItemHistoryRead, PendingItemListResponse, PendingItemProgressUpdate, PendingItemReactivate, PendingItemRead, PendingItemState, PendingItemUpdate, PendingItemVersion
from app.services.v2_pending_item import PendingItemConflictError, PendingItemNotFoundError, PendingItemReferenceUnavailableError, correct_pending_item, create_pending_item, deactivate_pending_item, delete_pending_item, get_pending_item, list_pending_item_history, list_pending_items, pending_item_projection, reactivate_pending_item, update_pending_item, update_pending_progress


router = APIRouter(prefix="/workspaces/{workspace_id}/pending-items", tags=["V2 Pending Items"])


def _raise(error: Exception) -> None:
    if isinstance(error, (PendingItemNotFoundError, PendingItemReferenceUnavailableError)):
        code = "PENDING_ITEM_NOT_FOUND" if isinstance(error, PendingItemNotFoundError) else "PENDING_ITEM_REFERENCE_UNAVAILABLE"
        raise V2APIError(status_code=404, code=code, message="No se encontró el Pendiente o una referencia disponible.") from error
    raise V2APIError(status_code=409, code="PENDING_ITEM_CONFLICT", message="El Pendiente cambió o no admite esta acción.") from error


def _read(db: SessionDependency, item: PendingItem, today: date, *, category=None, responsible=None) -> PendingItemRead:
    category, responsible, state, compliance, detail, can_edit, can_progress, can_correct, can_deactivate, can_reactivate, can_delete = pending_item_projection(db, item=item, local_date=today, category=category, responsible=responsible)
    return PendingItemRead(
        id=item.id, workspace_id=item.workspace_id, category_id=item.category_id, category_name=category.name,
        responsible_user_id=item.responsible_user_id, responsible_display_name=f"{responsible.first_name} {responsible.last_name}".strip(), responsible_email=responsible.email,
        name=item.name, is_active=item.is_active, planned_date=item.planned_date, progress=item.progress,
        state=state, completion_date=item.completion_date, compliance=compliance, compliance_detail_days=detail,
        lock_version=item.lock_version, can_edit=can_edit, can_update_progress=can_progress, can_correct=can_correct,
        can_deactivate=can_deactivate, can_reactivate=can_reactivate, can_delete=can_delete,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def _write(db: SessionDependency, operation):
    try:
        result = operation()
        db.commit()
        if result is not None:
            db.refresh(result)
        return result
    except (PendingItemNotFoundError, PendingItemConflictError, PendingItemReferenceUnavailableError) as error:
        db.rollback()
        _raise(error)
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=PendingItemRead, status_code=status.HTTP_201_CREATED)
def create(workspace_id: uuid.UUID, item_in: PendingItemCreate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    item = _write(db, lambda: create_pending_item(db, access=access, actor=account, item_in=item_in))
    return _read(db, item, local_today(account.timezone))


@router.get("", response_model=PendingItemListResponse)
def index(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), is_active: bool | None = None, responsible_user_id: uuid.UUID | None = None, category_id: uuid.UUID | None = None, state: PendingItemState | None = None, compliance: PendingItemCompliance | None = None, planned_from: date | None = None, planned_to: date | None = None, search: str | None = Query(default=None, max_length=255)) -> PendingItemListResponse:
    del access
    if planned_from is not None and planned_to is not None and planned_from > planned_to:
        raise V2APIError(status_code=422, code="INVALID_DATE_RANGE", message="El rango de fechas no es válido.")
    today = local_today(account.timezone)
    try:
        rows, total = list_pending_items(db, workspace_id=workspace_id, local_date=today, page=page, page_size=page_size, is_active=is_active, responsible_user_id=responsible_user_id, category_id=category_id, state=state, compliance=compliance, planned_from=planned_from, planned_to=planned_to, search=search.strip() if search else None)
    except PendingItemReferenceUnavailableError as error:
        _raise(error)
    return PendingItemListResponse(items=[_read(db, item, today, category=category, responsible=responsible) for item, category, responsible in rows], total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size))


@router.get("/{pending_item_id}", response_model=PendingItemRead)
def detail(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del access
    try:
        return _read(db, get_pending_item(db, workspace_id=workspace_id, pending_item_id=pending_item_id), local_today(account.timezone))
    except PendingItemNotFoundError as error:
        _raise(error)


@router.get("/{pending_item_id}/history", response_model=PendingItemHistoryListResponse)
def history(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemHistoryListResponse:
    del account, access
    try:
        rows = list_pending_item_history(db, workspace_id=workspace_id, pending_item_id=pending_item_id)
    except PendingItemNotFoundError as error:
        _raise(error)
    return PendingItemHistoryListResponse(items=[PendingItemHistoryRead(id=entry.id, progress=entry.progress, comment=entry.comment, type=entry.event_type, actor_user_id=actor.id, actor_display_name=f"{actor.first_name} {actor.last_name}".strip(), recorded_at=entry.recorded_at) for entry, actor in rows])


@router.patch("/{pending_item_id}", response_model=PendingItemRead)
def patch(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, item_in: PendingItemUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    item = _write(db, lambda: update_pending_item(db, access=access, pending_item_id=pending_item_id, item_in=item_in))
    return _read(db, item, local_today(account.timezone))


@router.post("/{pending_item_id}/progress", response_model=PendingItemRead)
def progress(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, item_in: PendingItemProgressUpdate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    today = local_today(account.timezone)
    item = _write(db, lambda: update_pending_progress(db, access=access, actor=account, pending_item_id=pending_item_id, progress=item_in.progress, expected_version=item_in.lock_version, local_date=today, comment=item_in.comment))
    return _read(db, item, today)


@router.post("/{pending_item_id}/correction", response_model=PendingItemRead)
def correction(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, item_in: PendingItemCorrection, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    item = _write(db, lambda: correct_pending_item(db, access=access, actor=account, pending_item_id=pending_item_id, progress=item_in.progress, expected_version=item_in.lock_version, comment=item_in.comment))
    return _read(db, item, local_today(account.timezone))


@router.post("/{pending_item_id}/deactivate", response_model=PendingItemRead)
def deactivate(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, item_in: PendingItemVersion, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    item = _write(db, lambda: deactivate_pending_item(db, access=access, pending_item_id=pending_item_id, expected_version=item_in.lock_version))
    return _read(db, item, local_today(account.timezone))


@router.post("/{pending_item_id}/reactivate", response_model=PendingItemRead)
def reactivate(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, item_in: PendingItemReactivate, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership) -> PendingItemRead:
    del workspace_id
    item = _write(db, lambda: reactivate_pending_item(db, access=access, pending_item_id=pending_item_id, planned_date=item_in.planned_date, expected_version=item_in.lock_version))
    return _read(db, item, local_today(account.timezone))


@router.delete("/{pending_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(workspace_id: uuid.UUID, pending_item_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, lock_version: int = Query(ge=1)) -> Response:
    del workspace_id, account
    _write(db, lambda: delete_pending_item(db, access=access, pending_item_id=pending_item_id, expected_version=lock_version))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
