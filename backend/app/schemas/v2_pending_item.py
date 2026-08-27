import unicodedata
import uuid

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PendingItemState = Literal["NO_INICIADO", "EN_PROCESO", "FINALIZADO"]
PendingItemCompliance = Literal["EN_PLAZO", "ATRASADO", "A_TIEMPO", "CON_ADELANTO", "CON_RETRASO"]


def clean_pending_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", " ".join(value.split()))
    if not cleaned:
        raise ValueError("Pending Item name cannot be blank")
    if len(cleaned) > 255:
        raise ValueError("Pending Item name must not exceed 255 characters")
    return cleaned


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PendingItemCreate(_StrictModel):
    category_id: uuid.UUID
    responsible_user_id: uuid.UUID | None = None
    name: str
    planned_date: date

    _name = field_validator("name")(clean_pending_name)


class PendingItemUpdate(_StrictModel):
    category_id: uuid.UUID | None = None
    responsible_user_id: uuid.UUID | None = None
    name: str | None = None
    planned_date: date | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_and_empty(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("category_id", "responsible_user_id", "name", "planned_date"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
            if not any(field in value for field in ("category_id", "responsible_user_id", "name", "planned_date")):
                raise ValueError("At least one editable field is required")
        return value

    _name = field_validator("name")(clean_pending_name)


class PendingItemProgressUpdate(_StrictModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = Field(default=None, max_length=2000)
    lock_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_action(self) -> "PendingItemProgressUpdate":
        if self.comment is not None:
            self.comment = clean_pending_comment(self.comment)
        if self.progress is None and self.comment is None:
            raise ValueError("Progress or comment is required")
        return self


class PendingItemCorrection(_StrictModel):
    progress: int = Field(ge=0, le=99)
    comment: str | None = Field(default=None, max_length=2000)
    lock_version: int = Field(ge=1)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        return None if value is None else clean_pending_comment(value)


def clean_pending_comment(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", value.strip())
    if not cleaned:
        raise ValueError("Comment cannot be blank")
    if any(unicodedata.category(character) == "Cc" and character not in "\n\t" for character in cleaned):
        raise ValueError("Comment must not contain control characters")
    return cleaned


class PendingItemReactivate(_StrictModel):
    planned_date: date
    lock_version: int = Field(ge=1)


class PendingItemVersion(_StrictModel):
    lock_version: int = Field(ge=1)


class PendingItemRead(_StrictModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    responsible_user_id: uuid.UUID
    responsible_display_name: str
    responsible_email: str
    name: str
    is_active: bool
    planned_date: date | None
    progress: int
    state: PendingItemState
    completion_date: date | None
    compliance: PendingItemCompliance | None
    compliance_detail_days: int | None
    lock_version: int
    can_edit: bool
    can_update_progress: bool
    can_correct: bool
    can_deactivate: bool
    can_reactivate: bool
    can_delete: bool
    created_at: datetime
    updated_at: datetime


class PendingItemListResponse(_StrictModel):
    items: list[PendingItemRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class PendingItemHistoryRead(_StrictModel):
    id: uuid.UUID
    progress: int = Field(ge=0, le=100)
    comment: str | None
    type: Literal["TRACKING", "CORRECTION"]
    actor_user_id: uuid.UUID
    actor_display_name: str
    recorded_at: datetime


class PendingItemHistoryListResponse(_StrictModel):
    items: list[PendingItemHistoryRead]
