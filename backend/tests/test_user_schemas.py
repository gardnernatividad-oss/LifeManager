import uuid

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import User
from app.schemas.user import UserCreate, UserRead, UserUpdate


def test_registration_schema_contains_only_target_fields() -> None:
    schema = UserCreate(
        email="ada@example.com",
        password="plain-secret",
        first_name=" Ada ",
        last_name=" Lovelace ",
    )

    assert schema.model_dump() == {
        "email": "ada@example.com",
        "password": "plain-secret",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }


@pytest.mark.parametrize("field_name", ["username", "full_name", "language", "timezone"])
def test_registration_schema_rejects_obsolete_or_unapproved_fields(field_name: str) -> None:
    payload = {
        "email": "ada@example.com",
        "password": "plain-secret",
        "first_name": "Ada",
        "last_name": "Lovelace",
        field_name: "unexpected",
    }

    with pytest.raises(ValidationError):
        UserCreate.model_validate(payload)


@pytest.mark.parametrize("timezone_name", ["America/Lima", "Europe/London", "Asia/Tokyo"])
def test_profile_update_accepts_valid_iana_timezone(timezone_name: str) -> None:
    assert UserUpdate(timezone=timezone_name).timezone == timezone_name


@pytest.mark.parametrize("timezone_name", ["", "   ", "Lima", "Mars/Olympus_Mons"])
def test_profile_update_rejects_invalid_timezone(timezone_name: str) -> None:
    with pytest.raises(ValidationError, match="valid IANA identifier"):
        UserUpdate(timezone=timezone_name)


def test_profile_update_rejects_email_and_explicit_nulls() -> None:
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"email": "new@example.com"})
    with pytest.raises(ValidationError, match="timezone cannot be null"):
        UserUpdate.model_validate({"timezone": None})


def test_user_read_exposes_timezone_without_password_data() -> None:
    timestamp = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        hashed_password="secret-hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        is_active=True,
        is_verified=False,
        created_at=timestamp,
        updated_at=timestamp,
    )

    payload = UserRead.model_validate(user).model_dump()

    assert payload["timezone"] == "America/Lima"
    assert "password" not in payload
    assert "hashed_password" not in payload
