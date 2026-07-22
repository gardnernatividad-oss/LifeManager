import uuid

from datetime import datetime

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


def validate_workspace_timezone(value: str) -> str:
    try:
        return ZoneInfo(value).key
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("timezone must be a valid IANA identifier") from error


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None
    timezone: str = "America/Lima"

    _timezone = field_validator("timezone")(validate_workspace_timezone)


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_valid(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("timezone cannot be null")
        return validate_workspace_timezone(value)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    timezone: str
    created_at: datetime
    updated_at: datetime
