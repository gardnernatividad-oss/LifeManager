import uuid

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def validate_user_timezone(value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("timezone must be a valid IANA identifier")
    try:
        return ZoneInfo(cleaned_value).key
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("timezone must be a valid IANA identifier") from error


def _clean_name(value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("name must not be blank")
    return cleaned_value


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)

    _clean_names = field_validator("first_name", "last_name")(_clean_name)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: object) -> object:
        if isinstance(value, dict):
            for field_name in ("first_name", "last_name", "timezone"):
                if field_name in value and value[field_name] is None:
                    raise ValueError(f"{field_name} cannot be null")
        return value

    _clean_names = field_validator("first_name", "last_name")(_clean_name)
    _validate_timezone = field_validator("timezone")(validate_user_timezone)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    timezone: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
