import uuid

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


CategoryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
CategoryDescription = Annotated[str, StringConstraints(max_length=500)]


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CategoryName
    description: CategoryDescription | None = None


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CategoryName | None = None
    description: CategoryDescription | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
