import uuid

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.names import normalize_name


def _clean_category_name(value: str) -> str:
    return normalize_name(value, max_length=100, field_label="Category")[0]


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str

    _name = field_validator("name")(_clean_category_name)


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("name", ...) is None:
            raise ValueError("name cannot be null")
        return value

    _name = field_validator("name")(_clean_category_name)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    items: list[CategoryRead]
    total: int
    page: int
    page_size: int
    total_pages: int
