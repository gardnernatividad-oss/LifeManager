import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import PendingItem, ProjectStep, Task, User
from app.schemas.user import UserUpdate
from app.services.user import update_user_profile


@pytest.fixture
def configuration_context():
    db = MagicMock(spec=Session)
    timestamp = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        hashed_password="hash",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        is_active=True,
        is_verified=False,
        created_at=timestamp,
        updated_at=timestamp,
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, db, user
    app.dependency_overrides.clear()


def test_profile_read_exposes_target_identity_without_sensitive_or_legacy_settings(
    configuration_context,
) -> None:
    client, db, user = configuration_context
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == "ada@example.com"
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["timezone"] == "America/Lima"
    assert set(body) == {"id", "email", "first_name", "last_name", "timezone"}
    for field in (
        "password",
        "hashed_password",
        "locale",
        "week_starts_on",
        "daily_form_enabled",
        "review_time",
        "workspace_timezone",
    ):
        assert field not in body
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_profile_update_trims_partial_names_changes_timezone_and_commits_once(
    configuration_context,
) -> None:
    client, db, user = configuration_context
    response = client.patch(
        "/api/v1/auth/me",
        json={
            "first_name": "  Augusta  ",
            "last_name": "  King  ",
            "timezone": "Europe/Madrid",
        },
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Augusta"
    assert response.json()["last_name"] == "King"
    assert response.json()["timezone"] == "Europe/Madrid"
    assert user.email == "ada@example.com"
    db.flush.assert_called_once_with()
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": "   "},
        {"last_name": "   "},
        {"timezone": "Not/A-Timezone"},
        {"timezone": None},
        {"email": "changed@example.com"},
        {"locale": "es-PE"},
        {"week_starts_on": "SUNDAY"},
        {"daily_form_enabled": True},
        {"task_reminder_enabled": True},
        {"workspace_timezone": "UTC"},
    ],
)
def test_profile_update_rejects_invalid_null_read_only_and_obsolete_fields(
    configuration_context, payload
) -> None:
    client, db, _user = configuration_context
    response = client.patch("/api/v1/auth/me", json=payload)
    assert response.status_code == 422
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_unexpected_profile_update_failure_rolls_back_without_commit(
    configuration_context,
) -> None:
    client, db, _user = configuration_context
    with patch(
        "app.api.routes.auth.update_user_profile",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            client.patch("/api/v1/auth/me", json={"first_name": "Augusta"})
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "timezone_name",
    ["America/Lima", "Pacific/Kiritimati", "Pacific/Honolulu"],
)
def test_profile_schema_accepts_representative_iana_timezones(timezone_name: str) -> None:
    assert UserUpdate(timezone=timezone_name).timezone == timezone_name


def test_timezone_change_preserves_historical_business_dates() -> None:
    db = MagicMock(spec=Session)
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
    )
    task = Task(planned_date=date(2026, 8, 10))
    pending_item = PendingItem(
        planned_date=date(2026, 8, 11), completion_date=date(2026, 8, 12)
    )
    step = ProjectStep(
        planned_date=date(2026, 8, 13), completion_date=date(2026, 8, 14)
    )
    historical_dates = (
        task.planned_date,
        pending_item.planned_date,
        pending_item.completion_date,
        step.planned_date,
        step.completion_date,
    )
    update_user_profile(
        db,
        user=user,
        user_in=UserUpdate(timezone="Pacific/Kiritimati"),
    )
    assert user.timezone == "Pacific/Kiritimati"
    assert historical_dates == (
        task.planned_date,
        pending_item.planned_date,
        pending_item.completion_date,
        step.planned_date,
        step.completion_date,
    )
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_timezone_list_is_authenticated_sorted_unique_and_read_only(
    configuration_context,
) -> None:
    client, db, _user = configuration_context
    zones = {"Pacific/Kiritimati", "America/Lima", "Europe/Madrid", "Pacific/Honolulu"}
    with patch("app.api.v1.timezones.available_timezones", return_value=zones):
        response = client.get("/api/v1/timezones")
    assert response.status_code == 200
    assert response.json() == {"items": sorted(zones)}
    assert len(response.json()["items"]) == len(set(response.json()["items"]))
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()

    real_response = client.get("/api/v1/timezones")
    assert real_response.status_code == 200
    real_items = real_response.json()["items"]
    assert real_items == sorted(real_items)
    assert len(real_items) == len(set(real_items))
    assert {"America/Lima", "Europe/Madrid", "Pacific/Kiritimati"} <= set(real_items)


def test_timezone_list_uses_real_standard_library_catalog_and_requires_authentication(
) -> None:
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/timezones")
    assert unauthenticated.status_code == 401

    zones = __import__("zoneinfo").available_timezones()
    assert "America/Lima" in zones
    assert "Europe/Madrid" in zones
    assert "Pacific/Kiritimati" in zones


def test_active_v1_openapi_has_no_legacy_settings_routes_or_fields(
    configuration_context,
) -> None:
    client, _db, _user = configuration_context
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]
    assert "/api/v1/user-settings" not in paths
    assert not any("workspace-settings" in path for path in paths)
    update_properties = openapi["components"]["schemas"]["UserUpdate"]["properties"]
    assert set(update_properties) == {"first_name", "last_name", "timezone"}


def test_explicit_null_names_are_rejected_by_strict_update_schema() -> None:
    for field in ("first_name", "last_name"):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({field: None})
