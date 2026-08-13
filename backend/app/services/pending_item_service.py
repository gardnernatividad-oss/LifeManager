import uuid

from datetime import date, datetime, timezone

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models import Category, PendingItem, User, WorkspaceTrackingMetadata
from app.schemas.pending_item import (
    PendingItemCompliance,
    PendingItemCreate,
    PendingItemPlanningUpdate,
    PendingItemState,
    PendingItemTrackingBatch,
)


class PendingItemNotFoundError(LookupError):
    pass


class PendingItemCategoryNotFoundError(LookupError):
    pass


class PendingItemConflictError(ValueError):
    pass


class PendingItemVersionConflictError(ValueError):
    pass


def _options():
    return selectinload(PendingItem.category)


def _get_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    for_update: bool = False,
) -> Category:
    statement = select(Category).where(
        Category.id == category_id,
        Category.workspace_id == workspace_id,
    )
    if for_update:
        statement = statement.with_for_update()
    category = db.scalar(statement)
    if category is None:
        raise PendingItemCategoryNotFoundError("Category not found")
    return category


def _get_item(
    db: Session, *, workspace_id: uuid.UUID, pending_item_id: uuid.UUID
) -> PendingItem:
    item = db.scalar(
        select(PendingItem)
        .options(_options())
        .where(
            PendingItem.id == pending_item_id,
            PendingItem.workspace_id == workspace_id,
        )
    )
    if item is None:
        raise PendingItemNotFoundError("Pending Item not found")
    return item


def _normalized_planned_date(is_active: bool, planned_date: date | None) -> date | None:
    if is_active and planned_date is None:
        raise PendingItemConflictError("Active Pending Items require planned_date")
    return planned_date if is_active else None


def create_pending_item(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    item_in: PendingItemCreate,
) -> PendingItem:
    category = _get_category(
        db,
        workspace_id=workspace_id,
        category_id=item_in.category_id,
        for_update=True,
    )
    item = PendingItem(
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name=item_in.name,
        is_active=item_in.is_active,
        planned_date=_normalized_planned_date(
            item_in.is_active, item_in.planned_date
        ),
        progress=0,
        completion_date=None,
        comment=None,
        created_by_id=current_user.id,
        lock_version=1,
    )
    db.add(item)
    db.flush()
    return item


def list_pending_items(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    local_date: date,
    page: int,
    page_size: int,
    is_active: bool | None = None,
    unfinished: bool | None = None,
    category_id: uuid.UUID | None = None,
    state: PendingItemState | None = None,
    compliance: PendingItemCompliance | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
) -> tuple[list[PendingItem], int]:
    filters = [PendingItem.workspace_id == workspace_id]
    if is_active is not None:
        filters.append(PendingItem.is_active == is_active)
    if unfinished is True:
        filters.append(PendingItem.progress < 100)
    elif unfinished is False:
        filters.append(PendingItem.progress == 100)
    if category_id is not None:
        _get_category(db, workspace_id=workspace_id, category_id=category_id)
        filters.append(PendingItem.category_id == category_id)
    if planned_from is not None:
        filters.append(PendingItem.planned_date >= planned_from)
    if planned_to is not None:
        filters.append(PendingItem.planned_date <= planned_to)
    if state is PendingItemState.NO_INICIADO:
        filters.append(PendingItem.progress == 0)
    elif state is PendingItemState.EN_PROCESO:
        filters.append(PendingItem.progress.between(1, 99))
    elif state is PendingItemState.FINALIZADO:
        filters.append(PendingItem.progress == 100)
    if compliance is PendingItemCompliance.EN_PLAZO:
        filters.extend(
            (PendingItem.completion_date.is_(None), PendingItem.planned_date >= local_date)
        )
    elif compliance is PendingItemCompliance.ATRASADO:
        filters.extend(
            (PendingItem.completion_date.is_(None), PendingItem.planned_date < local_date)
        )
    elif compliance is PendingItemCompliance.CON_ADELANTO:
        filters.append(PendingItem.completion_date < PendingItem.planned_date)
    elif compliance is PendingItemCompliance.A_TIEMPO:
        filters.append(PendingItem.completion_date == PendingItem.planned_date)
    elif compliance is PendingItemCompliance.CON_RETRASO:
        filters.append(PendingItem.completion_date > PendingItem.planned_date)

    total = db.scalar(
        select(func.count()).select_from(PendingItem).where(*filters)
    ) or 0
    urgency = case(
        (
            and_(
                PendingItem.is_active.is_(True),
                PendingItem.progress < 100,
                PendingItem.planned_date < local_date,
            ),
            0,
        ),
        (
            and_(
                PendingItem.is_active.is_(True), PendingItem.progress < 100
            ),
            1,
        ),
        else_=2,
    )
    statement = (
        select(PendingItem)
        .options(_options())
        .where(*filters)
        .order_by(urgency, PendingItem.planned_date.asc().nulls_last(), PendingItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement).all()), int(total)


def get_pending_item(
    db: Session, *, workspace_id: uuid.UUID, pending_item_id: uuid.UUID
) -> PendingItem:
    return _get_item(
        db, workspace_id=workspace_id, pending_item_id=pending_item_id
    )


def update_pending_item(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    pending_item_id: uuid.UUID,
    item_in: PendingItemPlanningUpdate,
) -> PendingItem:
    item = _get_item(
        db, workspace_id=workspace_id, pending_item_id=pending_item_id
    )
    if item.lock_version != item_in.lock_version:
        raise PendingItemVersionConflictError("Pending Item version is stale")
    changes = item_in.model_dump(exclude_unset=True, exclude={"lock_version"})
    category: Category | None = None
    if (
        "category_id" in changes
        and changes["category_id"] != item.category_id
    ):
        category = _get_category(
            db,
            workspace_id=workspace_id,
            category_id=changes["category_id"],
            for_update=True,
        )
        changes["category_id"] = category.id
    target_active = changes.get("is_active", item.is_active)
    target_date = changes.get("planned_date", item.planned_date)
    changes["planned_date"] = _normalized_planned_date(target_active, target_date)
    result = db.execute(
        update(PendingItem)
        .where(
            PendingItem.id == pending_item_id,
            PendingItem.workspace_id == workspace_id,
            PendingItem.lock_version == item_in.lock_version,
        )
        .values(**changes, lock_version=PendingItem.lock_version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise PendingItemVersionConflictError("Pending Item version is stale")
    for field, value in changes.items():
        set_committed_value(item, field, value)
    if category is not None:
        set_committed_value(item, "category", category)
    set_committed_value(item, "lock_version", item_in.lock_version + 1)
    db.flush()
    return item


def list_review_eligible_pending_items(
    db: Session, *, workspace_id: uuid.UUID, local_date: date
) -> list[PendingItem]:
    statement = (
        select(PendingItem)
        .options(_options())
        .where(
            PendingItem.workspace_id == workspace_id,
            PendingItem.is_active.is_(True),
            PendingItem.progress < 100,
            PendingItem.planned_date <= local_date,
        )
        .order_by(PendingItem.planned_date, PendingItem.id)
    )
    return list(db.scalars(statement).all())


def save_pending_item_tracking(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    tracking_in: PendingItemTrackingBatch,
    local_date: date,
    saved_at: datetime | None = None,
) -> tuple[list[PendingItem], datetime]:
    expected = {row.id: row for row in tracking_in.items}
    items = list(
        db.scalars(
            select(PendingItem)
            .options(_options())
            .where(
                PendingItem.workspace_id == workspace_id,
                PendingItem.id.in_(expected),
            )
            .order_by(PendingItem.id)
            .with_for_update()
        ).all()
    )
    if len(items) != len(expected):
        raise PendingItemNotFoundError("One or more Pending Items were not found")
    if any(item.lock_version != expected[item.id].lock_version for item in items):
        raise PendingItemVersionConflictError(
            "One or more Pending Item versions are stale"
        )

    for item in items:
        row = expected[item.id]
        changes = row.model_dump(exclude_unset=True, exclude={"id", "lock_version"})
        is_active = changes.get("is_active", item.is_active)
        if not is_active:
            changes["planned_date"] = None
        elif item.planned_date is None:
            raise PendingItemConflictError(
                "Active Pending Items require planned_date"
            )
        if "progress" in changes:
            if changes["progress"] == 100 and item.progress < 100:
                changes["completion_date"] = local_date
            elif changes["progress"] < 100:
                changes["completion_date"] = None
        result = db.execute(
            update(PendingItem)
            .where(
                PendingItem.id == item.id,
                PendingItem.workspace_id == workspace_id,
                PendingItem.lock_version == row.lock_version,
            )
            .values(**changes, lock_version=PendingItem.lock_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise PendingItemVersionConflictError(
                "One or more Pending Item versions are stale"
            )
        for field, value in changes.items():
            set_committed_value(item, field, value)
        set_committed_value(item, "lock_version", row.lock_version + 1)

    timestamp = saved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("saved_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    metadata = db.get(WorkspaceTrackingMetadata, workspace_id)
    if metadata is None:
        metadata = WorkspaceTrackingMetadata(workspace_id=workspace_id)
        db.add(metadata)
    metadata.pending_items_last_tracking_saved_at = timestamp
    db.flush()
    return items, timestamp
