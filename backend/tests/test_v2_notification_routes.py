import uuid

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_usable_account
from app.main import app
from app.models import PushSubscription, User
from app.services.v2_notifications import get_preferences


def _client():
    user = User(id=uuid.uuid4(), email="notify@test.local", first_name="Ana", last_name="Uno", timezone="America/Lima")
    db = MagicMock(); db.scalars.return_value.all.return_value = []
    app.dependency_overrides[get_db] = lambda: db; app.dependency_overrides[get_current_account] = lambda: user; app.dependency_overrides[require_usable_account] = lambda: user
    return TestClient(app), user, db


def test_preferences_defaults_auth_and_strict_contract() -> None:
    client, _, db = _client()
    try:
        response = client.get("/api/v2/notification-preferences")
        assert response.status_code == 200 and response.json()["daily_summary"]["local_time"] == "07:00:00"
        db.commit.assert_not_called(); db.flush.assert_not_called()
        invalid = response.json(); invalid["timezone"] = "UTC"
        assert client.put("/api/v2/notification-preferences", json=invalid).status_code == 422
    finally: app.dependency_overrides.clear()
    assert TestClient(app).get("/api/v2/notification-preferences").status_code == 401


def test_push_register_uses_current_account_and_delete_is_scoped() -> None:
    client, user, db = _client(); subscription_id = uuid.uuid4()
    row = PushSubscription(id=subscription_id, user_id=user.id, is_active=True, endpoint_hash=b"x", endpoint_ciphertext=b"x", p256dh_ciphertext=b"x", auth_ciphertext=b"x")
    try:
        with patch("app.api.v2.notifications.register_push_subscription", return_value=row) as register:
            response = client.post("/api/v2/push-subscriptions", json={"endpoint": "https://push.example/sub", "keys": {"p256dh": "key", "auth": "auth"}})
        assert response.status_code == 201 and "endpoint" not in response.json()
        assert register.call_args.kwargs["user_id"] == user.id and db.commit.call_count == 1
        with patch("app.api.v2.notifications.unregister_push_subscription") as unregister:
            assert client.delete(f"/api/v2/push-subscriptions/{subscription_id}").status_code == 204
        assert unregister.call_args.kwargs["user_id"] == user.id
    finally: app.dependency_overrides.clear()


def test_openapi_exposes_only_user_contracts() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v2/notification-preferences" in paths and "/api/v2/push-subscriptions" in paths
    assert all("scheduler" not in path and "send-notification" not in path for path in paths)
