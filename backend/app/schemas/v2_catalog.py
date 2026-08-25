import uuid
import unicodedata

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.names import normalize_name


def _clean_name(value: str, *, max_length: int, label: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("name must not contain control characters")
    return normalize_name(value, max_length=max_length, field_label=label)[0]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryCreate(_StrictModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value, max_length=100, label="Category")


class CategoryUpdate(_StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_name(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("name", ...) is None:
            raise ValueError("name cannot be null")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value, max_length=100, label="Category")


class CatalogLifecycleUpdate(_StrictModel):
    lock_version: int = Field(ge=1)


class CategoryRead(_StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    is_active: bool
    lock_version: int
    created_at: datetime
    updated_at: datetime


class CatalogItemCreate(_StrictModel):
    name: str = Field(min_length=1, max_length=150)
    category_id: uuid.UUID

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value, max_length=150, label="Catalog item")


class CatalogItemUpdate(_StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category_id: uuid.UUID | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("name", "category_id"):
                if value.get(field, ...) is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value, max_length=150, label="Catalog item")


class CatalogItemRead(_StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    category_name: str
    is_active: bool
    lock_version: int
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(_StrictModel):
    items: list[CategoryRead]
    total: int = Field(ge=0)


class CatalogItemListResponse(_StrictModel):
    items: list[CatalogItemRead]
    total: int = Field(ge=0)
