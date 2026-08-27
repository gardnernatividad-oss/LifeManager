import unicodedata
import uuid

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProjectStageState = Literal["NO_INICIADA", "EN_PROCESO", "FINALIZADA"]
ProjectCompliance = Literal["EN_PLAZO", "ATRASADO", "A_TIEMPO", "CON_ADELANTO", "CON_RETRASO"]


def clean_stage_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", " ".join(value.split()))
    if not cleaned:
        raise ValueError("Stage name cannot be blank")
    if len(cleaned) > 255:
        raise ValueError("Stage name must not exceed 255 characters")
    return cleaned


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectStageCreate(_StrictModel):
    responsible_user_id: uuid.UUID | None = None
    name: str
    position: int = Field(ge=0)
    weight: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    planned_date: date
    project_lock_version: int = Field(ge=1)

    _name = field_validator("name")(clean_stage_name)


class ProjectStageUpdate(_StrictModel):
    responsible_user_id: uuid.UUID | None = None
    name: str | None = None
    position: int | None = Field(default=None, ge=0)
    weight: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    planned_date: date | None = None
    lock_version: int = Field(ge=1)
    project_lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def require_update(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("responsible_user_id", "name", "position", "weight", "planned_date"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
            if not any(field in value for field in ("responsible_user_id", "name", "position", "weight", "planned_date")):
                raise ValueError("At least one editable field is required")
        return value

    _name = field_validator("name")(clean_stage_name)


class ProjectStageProgress(_StrictModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = Field(default=None, max_length=2000)
    lock_version: int = Field(ge=1)
    project_lock_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_progress_or_comment(self) -> "ProjectStageProgress":
        if self.comment is not None:
            self.comment = self.comment.strip()
            if not self.comment:
                raise ValueError("Comment cannot be blank")
        if self.progress is None and self.comment is None:
            raise ValueError("Progress or comment is required")
        return self


class ProjectStageRead(_StrictModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    responsible_user_id: uuid.UUID
    responsible_display_name: str
    responsible_email: str
    name: str
    position: int
    weight: Decimal
    planned_date: date
    progress: int
    state: ProjectStageState
    completion_date: date | None
    compliance: ProjectCompliance
    compliance_detail_days: int
    lock_version: int
    can_edit: bool
    can_update_progress: bool
    created_at: datetime
    updated_at: datetime


class ProjectStageListResponse(_StrictModel):
    items: list[ProjectStageRead]
    total_weight: Decimal
    weights_complete: bool


class ProjectStageHistoryRead(_StrictModel):
    id: uuid.UUID
    progress: int
    comment: str | None
    type: Literal["TRACKING", "CORRECTION"]
    actor_user_id: uuid.UUID
    actor_display_name: str
    recorded_at: datetime


class ProjectStageHistoryListResponse(_StrictModel):
    items: list[ProjectStageHistoryRead]
