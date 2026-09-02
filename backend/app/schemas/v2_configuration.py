import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.password_policy import validate_password_policy
from app.schemas.v2_identity import _clean_name, _timezone


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    timezone: str
    lock_version: int


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    timezone: str = Field(max_length=100)
    lock_version: int = Field(ge=1)

    _clean_names = field_validator("first_name", "last_name")(_clean_name)
    _validate_timezone = field_validator("timezone")(_timezone)


class TimezoneList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    _validate_new_password = field_validator("new_password")(
        validate_password_policy
    )
