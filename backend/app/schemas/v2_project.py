import unicodedata
import uuid

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def clean_project_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", " ".join(value.split()))
    if not cleaned:
        raise ValueError("Project name cannot be blank")
    if len(cleaned) > 255:
        raise ValueError("Project name must not exceed 255 characters")
    return cleaned


def clean_project_description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = unicodedata.normalize("NFC", value.strip())
    return cleaned or None


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(_StrictModel):
    category_id: uuid.UUID
    leader_user_id: uuid.UUID | None = None
    name: str
    description: str | None = None

    _name = field_validator("name")(clean_project_name)
    _description = field_validator("description")(clean_project_description)


class ProjectUpdate(_StrictModel):
    category_id: uuid.UUID | None = None
    leader_user_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def require_update(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("category_id", "leader_user_id", "name"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
            if not any(field in value for field in ("category_id", "leader_user_id", "name", "description")):
                raise ValueError("At least one editable field is required")
        return value

    _name = field_validator("name")(clean_project_name)
    _description = field_validator("description")(clean_project_description)


class ProjectVersion(_StrictModel):
    lock_version: int = Field(ge=1)


class ProjectRead(_StrictModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    leader_user_id: uuid.UUID
    leader_display_name: str
    leader_email: str
    name: str
    description: str | None
    is_active: bool
    planned_date: date | None
    progress: float | None
    state: str | None
    compliance: str | None
    compliance_detail_days: int | None
    completion_date: date | None
    weights_complete: bool
    stage_count: int = Field(ge=0)
    total_weight: Decimal = Field(ge=0, le=100)
    lock_version: int
    can_edit: bool
    can_deactivate: bool
    can_reactivate: bool
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(_StrictModel):
    items: list[ProjectRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
