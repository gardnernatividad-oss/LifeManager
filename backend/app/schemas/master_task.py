import uuid

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.names import normalize_name
from app.schemas.category import CategoryRead


def _clean_master_task_name(value: str) -> str:
    return normalize_name(value, max_length=150, field_label="Master task")[0]


class MasterTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category_id: uuid.UUID

    _name = field_validator("name")(_clean_master_task_name)


class MasterTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    category_id: uuid.UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: object) -> object:
        if isinstance(value, dict):
            for field_name in ("name", "category_id"):
                if value.get(field_name, ...) is None:
                    raise ValueError(f"{field_name} cannot be null")
        return value

    _name = field_validator("name")(_clean_master_task_name)


class MasterTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_id: uuid.UUID
    category: CategoryRead
    created_at: datetime
    updated_at: datetime


class MasterTaskListResponse(BaseModel):
    items: list[MasterTaskRead]
    total: int
    page: int
    page_size: int
    total_pages: int
