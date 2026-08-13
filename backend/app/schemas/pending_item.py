import enum
import unicodedata
import uuid

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import PendingItem


class PendingItemState(str, enum.Enum):
    NO_INICIADO = "NO_INICIADO"
    EN_PROCESO = "EN_PROCESO"
    FINALIZADO = "FINALIZADO"


class PendingItemCompliance(str, enum.Enum):
    EN_PLAZO = "EN_PLAZO"
    ATRASADO = "ATRASADO"
    CON_ADELANTO = "CON_ADELANTO"
    A_TIEMPO = "A_TIEMPO"
    CON_RETRASO = "CON_RETRASO"


def _clean_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", " ".join(value.split()))
    if not cleaned:
        raise ValueError("Pending Item name cannot be blank")
    if len(cleaned) > 255:
        raise ValueError("Pending Item name must not exceed 255 characters")
    return cleaned


def derive_pending_item_state(progress: int) -> PendingItemState:
    if progress == 0:
        return PendingItemState.NO_INICIADO
    if progress == 100:
        return PendingItemState.FINALIZADO
    return PendingItemState.EN_PROCESO


def derive_pending_item_compliance(
    item: PendingItem, *, local_date: date
) -> tuple[PendingItemCompliance | None, int | None]:
    if item.planned_date is None:
        return None, None
    if item.completion_date is None:
        if item.planned_date >= local_date:
            return PendingItemCompliance.EN_PLAZO, (item.planned_date - local_date).days
        return PendingItemCompliance.ATRASADO, (local_date - item.planned_date).days
    if item.completion_date < item.planned_date:
        return PendingItemCompliance.CON_ADELANTO, (
            item.planned_date - item.completion_date
        ).days
    if item.completion_date == item.planned_date:
        return PendingItemCompliance.A_TIEMPO, 0
    return PendingItemCompliance.CON_RETRASO, (
        item.completion_date - item.planned_date
    ).days


class PendingItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    name: str
    is_active: bool
    planned_date: date | None = None

    _name = field_validator("name")(_clean_name)

    @model_validator(mode="after")
    def active_requires_planned_date(self) -> "PendingItemCreate":
        if self.is_active and self.planned_date is None:
            raise ValueError("Active Pending Items require planned_date")
        return self


class PendingItemPlanningUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    name: str | None = None
    is_active: bool | None = None
    planned_date: date | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("category_id", "name", "is_active"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    _name = field_validator("name")(_clean_name)

    @model_validator(mode="after")
    def require_a_planning_change(self) -> "PendingItemPlanningUpdate":
        if not (self.model_fields_set - {"lock_version"}):
            raise ValueError("At least one planning field is required")
        return self


class PendingItemTrackingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    is_active: bool | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("is_active", "progress"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    @model_validator(mode="after")
    def require_a_tracking_change(self) -> "PendingItemTrackingUpdate":
        if not (self.model_fields_set - {"id", "lock_version"}):
            raise ValueError("At least one tracking field is required")
        return self


class PendingItemTrackingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PendingItemTrackingUpdate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def ids_must_be_unique(
        cls, value: list[PendingItemTrackingUpdate]
    ) -> list[PendingItemTrackingUpdate]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("Pending Item IDs must be unique")
        return value


class PendingItemCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class PendingItemRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category: PendingItemCategoryRead
    name: str
    is_active: bool
    planned_date: date | None
    progress: int
    state: PendingItemState
    completion_date: date | None
    compliance: PendingItemCompliance | None
    detail_days: int | None
    comment: str | None
    lock_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_pending_item(
        cls, item: PendingItem, *, local_date: date
    ) -> "PendingItemRead":
        compliance, detail_days = derive_pending_item_compliance(
            item, local_date=local_date
        )
        return cls(
            id=item.id,
            category_id=item.category_id,
            category=PendingItemCategoryRead.model_validate(item.category),
            name=item.name,
            is_active=item.is_active,
            planned_date=item.planned_date,
            progress=item.progress,
            state=derive_pending_item_state(item.progress),
            completion_date=item.completion_date,
            compliance=compliance,
            detail_days=detail_days,
            comment=item.comment,
            lock_version=item.lock_version,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class PendingItemListResponse(BaseModel):
    items: list[PendingItemRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class PendingItemTrackingBatchResponse(BaseModel):
    items: list[PendingItemRead]
    saved_at: datetime
