import uuid

from datetime import date

from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, PendingItem, PendingItemHistory, User, WorkspaceMember
from app.models.enums import AccountStatus, HistoryEventType, MembershipStatus, WorkspaceKind
from app.schemas.v2_pending_item import PendingItemCreate, PendingItemUpdate
from app.services.v2_workspace import WorkspaceAccess


class PendingItemNotFoundError(LookupError):
    pass


class PendingItemConflictError(ValueError):
    pass


class PendingItemReferenceUnavailableError(ValueError):
    pass


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint in {
            "fk_pending_items_category_workspace",
            "fk_pending_items_responsible_membership",
            "fk_pending_items_creator_membership",
        }:
            raise PendingItemReferenceUnavailableError("Pending Item reference unavailable") from error
        raise


def _category(db: Session, *, workspace_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = db.scalar(
        select(Category)
        .where(Category.id == category_id, Category.workspace_id == workspace_id)
        .with_for_update()
    )
    if category is None or not category.is_active:
        raise PendingItemReferenceUnavailableError("Category unavailable")
    return category


def _responsible(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> User:
    row = db.execute(
        select(User, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            User.id == user_id,
            User.account_status == AccountStatus.ACTIVE,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise PendingItemReferenceUnavailableError("Responsible unavailable")
    return row[0]


def _item(db: Session, *, workspace_id: uuid.UUID, pending_item_id: uuid.UUID, lock: bool = False) -> PendingItem:
    statement = select(PendingItem).where(PendingItem.id == pending_item_id, PendingItem.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None:
        raise PendingItemNotFoundError("Pending Item not found")
    return item


def _check_version(item: PendingItem, expected: int) -> None:
    if item.lock_version != expected:
        raise PendingItemConflictError("Pending Item version conflict")


def create_pending_item(db: Session, *, access: WorkspaceAccess, actor: User, item_in: PendingItemCreate) -> PendingItem:
    _category(db, workspace_id=access.workspace.id, category_id=item_in.category_id)
    responsible_id = access.workspace.owner_user_id if access.workspace.kind == WorkspaceKind.PERSONAL else (item_in.responsible_user_id or actor.id)
    _responsible(db, workspace_id=access.workspace.id, user_id=responsible_id)
    item = PendingItem(
        workspace_id=access.workspace.id,
        category_id=item_in.category_id,
        responsible_user_id=responsible_id,
        name=item_in.name,
        is_active=True,
        planned_date=item_in.planned_date,
        progress=0,
        completion_date=None,
        created_by_user_id=actor.id,
    )
    db.add(item)
    _flush(db)
    return item


def list_pending_items(db: Session, *, workspace_id: uuid.UUID, local_date: date, page: int, page_size: int) -> tuple[list[PendingItem], int]:
    filters = [PendingItem.workspace_id == workspace_id]
    total = db.scalar(select(func.count()).select_from(PendingItem).where(*filters)) or 0
    urgency = case(
        (and_(PendingItem.is_active.is_(True), PendingItem.progress < 100, PendingItem.planned_date < local_date), 0),
        (and_(PendingItem.is_active.is_(True), PendingItem.progress < 100), 1),
        else_=2,
    )
    items = list(
        db.scalars(
            select(PendingItem)
            .where(*filters)
            .order_by(urgency, PendingItem.planned_date.asc().nulls_last(), PendingItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, int(total)


def get_pending_item(db: Session, *, workspace_id: uuid.UUID, pending_item_id: uuid.UUID) -> PendingItem:
    return _item(db, workspace_id=workspace_id, pending_item_id=pending_item_id)


def update_pending_item(db: Session, *, access: WorkspaceAccess, pending_item_id: uuid.UUID, item_in: PendingItemUpdate) -> PendingItem:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, item_in.lock_version)
    if not item.is_active or item.progress == 100:
        raise PendingItemConflictError("Pending Item is read-only")
    values = item_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    if "category_id" in values and values["category_id"] != item.category_id:
        _category(db, workspace_id=access.workspace.id, category_id=values["category_id"])
    if "responsible_user_id" in values and values["responsible_user_id"] != item.responsible_user_id:
        _responsible(db, workspace_id=access.workspace.id, user_id=values["responsible_user_id"])
    for field, value in values.items():
        setattr(item, field, value)
    item.lock_version += 1
    _flush(db)
    return item


def update_pending_progress(db: Session, *, access: WorkspaceAccess, actor: User, pending_item_id: uuid.UUID, progress: int, expected_version: int, local_date: date) -> PendingItem:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, expected_version)
    if not item.is_active or item.progress == 100 or item.progress == progress:
        raise PendingItemConflictError("Pending Item progress cannot be changed")
    item.progress = progress
    if progress == 100:
        item.completion_date = local_date
    item.lock_version += 1
    db.add(PendingItemHistory(pending_item_id=item.id, workspace_id=item.workspace_id, actor_user_id=actor.id, progress=progress, comment=None, event_type=HistoryEventType.TRACKING))
    _flush(db)
    return item


def correct_pending_item(db: Session, *, access: WorkspaceAccess, actor: User, pending_item_id: uuid.UUID, progress: int, expected_version: int) -> PendingItem:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, expected_version)
    if not item.is_active or item.progress != 100:
        raise PendingItemConflictError("Only a finalized Pending Item can be corrected")
    item.progress = progress
    item.completion_date = None
    item.lock_version += 1
    db.add(PendingItemHistory(pending_item_id=item.id, workspace_id=item.workspace_id, actor_user_id=actor.id, progress=progress, comment=None, event_type=HistoryEventType.CORRECTION))
    _flush(db)
    return item


def deactivate_pending_item(db: Session, *, access: WorkspaceAccess, pending_item_id: uuid.UUID, expected_version: int) -> PendingItem:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, expected_version)
    if not item.is_active or item.progress == 100:
        raise PendingItemConflictError("Pending Item cannot be deactivated")
    item.is_active = False
    item.planned_date = None
    item.lock_version += 1
    _flush(db)
    return item


def reactivate_pending_item(db: Session, *, access: WorkspaceAccess, pending_item_id: uuid.UUID, planned_date: date, expected_version: int) -> PendingItem:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, expected_version)
    if item.is_active or item.progress == 100:
        raise PendingItemConflictError("Pending Item cannot be reactivated")
    item.is_active = True
    item.planned_date = planned_date
    item.lock_version += 1
    _flush(db)
    return item


def delete_pending_item(db: Session, *, access: WorkspaceAccess, pending_item_id: uuid.UUID, expected_version: int) -> None:
    item = _item(db, workspace_id=access.workspace.id, pending_item_id=pending_item_id, lock=True)
    _check_version(item, expected_version)
    if item.progress != 0:
        raise PendingItemConflictError("Only a zero-progress Pending Item can be deleted")
    db.delete(item)
    _flush(db)


def pending_item_projection(db: Session, *, item: PendingItem, local_date: date) -> tuple[Category, User, str, str | None, int | None, bool, bool, bool, bool, bool, bool]:
    category = db.scalar(select(Category).where(Category.id == item.category_id, Category.workspace_id == item.workspace_id))
    responsible = db.scalar(select(User).where(User.id == item.responsible_user_id))
    if category is None or responsible is None:
        raise PendingItemNotFoundError("Pending Item not found")
    state = "NO_INICIADO" if item.progress == 0 else "FINALIZADO" if item.progress == 100 else "EN_PROCESO"
    compliance: str | None = None
    detail: int | None = None
    if item.planned_date is not None:
        if item.completion_date is None:
            if local_date <= item.planned_date:
                compliance, detail = "EN_PLAZO", (item.planned_date - local_date).days
            else:
                compliance, detail = "ATRASADO", (local_date - item.planned_date).days
        elif item.completion_date == item.planned_date:
            compliance, detail = "A_TIEMPO", 0
        elif item.completion_date < item.planned_date:
            compliance, detail = "CON_ADELANTO", (item.planned_date - item.completion_date).days
        else:
            compliance, detail = "CON_RETRASO", (item.completion_date - item.planned_date).days
    editable = item.is_active and item.progress < 100
    return category, responsible, state, compliance, detail, editable, editable, item.is_active and item.progress == 100, editable, not item.is_active, item.progress == 0
