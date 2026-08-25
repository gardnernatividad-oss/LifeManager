import uuid

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import WorkspaceKind, WorkspaceLifecycle


class ResponsibilityDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["REASSIGN", "DELETE"]
    target_user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "ResponsibilityDirective":
        if self.action == "REASSIGN" and self.target_user_id is None:
            raise ValueError("target_user_id is required for REASSIGN")
        if self.action == "DELETE" and self.target_user_id is not None:
            raise ValueError("target_user_id is not accepted for DELETE")
        return self


class MemberExitResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delete_all: bool = False
    tasks: ResponsibilityDirective | None = None
    pending_items: ResponsibilityDirective | None = None
    projects: ResponsibilityDirective | None = None
    project_stages: ResponsibilityDirective | None = None

    @model_validator(mode="after")
    def validate_delete_all(self) -> "MemberExitResolution":
        if self.delete_all and any(
            directive is not None
            for directive in (
                self.tasks,
                self.pending_items,
                self.projects,
                self.project_stages,
            )
        ):
            raise ValueError("delete_all cannot be combined with domain directives")
        return self


class OwnershipTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_user_id: uuid.UUID


class WorkspaceLifecycleRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    kind: WorkspaceKind
    lifecycle: WorkspaceLifecycle
    deactivated_at: datetime | None
    can_delete: bool
