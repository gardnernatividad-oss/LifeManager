import uuid

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import InvitationStatus


class WorkspaceInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class WorkspaceInvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    recipient_email: EmailStr
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
