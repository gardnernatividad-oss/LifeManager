import uuid

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AccountStatus, GlobalRole
from app.core.password_policy import validate_password_policy


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("name must not be blank")
    return cleaned


def _timezone(value: str) -> str:
    cleaned = value.strip()
    try:
        return ZoneInfo(cleaned).key
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError("timezone must be a valid IANA identifier") from error


class RegistrationRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    timezone: str = Field(default="America/Lima", max_length=100)
    turnstile_token: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    _clean_names = field_validator("first_name", "last_name")(_clean_name)
    _validate_timezone = field_validator("timezone")(_timezone)
    _validate_password = field_validator("password")(validate_password_policy)


class RegistrationRequestAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: Literal[True] = True


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class AuthenticatedAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    timezone: str
    global_role: GlobalRole | None


class EmailVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class EmailVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: Literal[True] = True
    pending_approval: Literal[True] = True


class EmailVerificationResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    turnstile_token: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class PasswordRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    turnstile_token: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)
    new_password: str

    _validate_new_password = field_validator("new_password")(
        validate_password_policy
    )


class PasswordResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password_reset: Literal[True] = True


class AdminAccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    timezone: str
    account_status: AccountStatus
    email_verified_at: datetime | None
    created_at: datetime


class AdminRegistrationList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminAccountSummary]
    total: int = Field(ge=0)


class RejectAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None
