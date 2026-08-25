import uuid
import unicodedata

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.names import normalize_name
from app.models.enums import WorkspaceKind, WorkspaceLifecycle


def _clean_workspace_name(value: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("name must not contain control characters")
    visible_name, _ = normalize_name(
        value,
        max_length=150,
        field_label="Workspace",
    )
    return visible_name


class SharedWorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)

    _clean_name = field_validator("name", mode="before")(
        _clean_workspace_name
    )


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    kind: Literal[WorkspaceKind.SHARED]


WorkspaceVisibleRole = Literal["Propietario", "Miembro"]


class WorkspaceSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    kind: WorkspaceKind
    lifecycle: WorkspaceLifecycle
    visible_role: WorkspaceVisibleRole
    can_manage: bool
    can_delete: bool
    timezone: str
