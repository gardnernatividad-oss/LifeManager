import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_personal_workspace
from app.main import app
from app.models import Category, PendingItem, User, Workspace, WorkspaceKind
from app.services.pending_item_service import (
    PendingItemNotFoundError,
    PendingItemVersionConflictError,
)


@pytest.fixture
def pending_routes():
    db = MagicMock(spec=Session)
    user = User(id=uuid.uuid4(), timezone="America/Lima", is_active=True)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client:
        yield client, db, user, workspace
    app.dependency_overrides.clear()


def _item(workspace_id, user_id, *, progress=0):
    timestamp = datetime.now(timezone.utc)
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud",
        normalized_name="salud", created_at=timestamp, updated_at=timestamp,
    )
    return PendingItem(
        id=uuid.uuid4(), workspace_id=workspace_id, category_id=category.id,
        category=category, name="Control", is_active=True,
        planned_date=date(2026, 8, 12), progress=progress,
        completion_date=date(2026, 8, 12) if progress == 100 else None,
        comment=None, created_by_id=user_id, lock_version=1,
        created_at=timestamp, updated_at=timestamp,
    )


def test_create_uses_personal_context_and_commits_once(pending_routes) -> None:
    client, db, user, workspace = pending_routes
    item = _item(workspace.id, user.id)
    with patch(
        "app.api.v1.pending_items.pending_item_service.create_pending_item",
        return_value=item,
    ) as service:
        response = client.post("/api/v1/pending-items", json={
            "category_id": str(item.category_id), "name": "Control",
            "is_active": True, "planned_date": "2026-08-12",
        })
    assert response.status_code == 201 and response.json()["state"] == "NO_INICIADO"
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["current_user"] is user
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(item)


def test_list_returns_tracking_fields_filters_and_pagination(pending_routes) -> None:
    client, db, user, workspace = pending_routes
    item = _item(workspace.id, user.id)
    with patch(
        "app.api.v1.pending_items._today",
        return_value=date(2026, 8, 12),
    ), patch(
        "app.api.v1.pending_items.pending_item_service.list_pending_items",
        return_value=([item], 26),
    ) as service:
        response = client.get(
            f"/api/v1/pending-items?page=2&page_size=25&is_active=true&unfinished=true"
            f"&category_id={item.category_id}&state=NO_INICIADO&compliance=EN_PLAZO"
            "&planned_from=2026-08-01&planned_to=2026-08-31"
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_pages"] == 2 and payload["items"][0]["category"]["name"] == "Salud"
    assert payload["items"][0]["compliance"] == "EN_PLAZO"
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    assert service.call_args.kwargs["local_date"] == date(2026, 8, 12)
    db.commit.assert_not_called(); db.flush.assert_not_called()


def test_planning_update_commits_and_tracking_fields_are_rejected(pending_routes) -> None:
    client, db, user, workspace = pending_routes
    item = _item(workspace.id, user.id)
    with patch(
        "app.api.v1.pending_items.pending_item_service.update_pending_item",
        return_value=item,
    ):
        response = client.patch(
            f"/api/v1/pending-items/{item.id}",
            json={"name": "Control", "lock_version": 1},
        )
    assert response.status_code == 200; db.commit.assert_called_once_with()
    response = client.patch(
        f"/api/v1/pending-items/{item.id}",
        json={"progress": 20, "lock_version": 1},
    )
    assert response.status_code == 422


def test_tracking_batch_commits_once_and_serializes_timestamp(pending_routes) -> None:
    client, db, user, workspace = pending_routes
    item = _item(workspace.id, user.id, progress=100)
    saved_at = datetime(2026, 8, 12, 20, tzinfo=timezone.utc)
    with patch(
        "app.api.v1.pending_items.pending_item_service.save_pending_item_tracking",
        return_value=([item], saved_at),
    ):
        response = client.patch("/api/v1/pending-items/tracking", json={
            "items": [{"id": str(item.id), "progress": 100, "lock_version": 1}]
        })
    assert response.status_code == 200
    assert response.json()["saved_at"] == "2026-08-12T20:00:00Z"
    db.commit.assert_called_once_with(); db.refresh.assert_called_once_with(item)


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(PendingItemNotFoundError("Pending Item not found"), 404),
     (PendingItemVersionConflictError("Pending Item version is stale"), 409)],
)
def test_write_errors_rollback(pending_routes, error, status_code) -> None:
    client, db, _user, _workspace = pending_routes
    with patch(
        "app.api.v1.pending_items.pending_item_service.save_pending_item_tracking",
        side_effect=error,
    ):
        response = client.patch("/api/v1/pending-items/tracking", json={
            "items": [{"id": str(uuid.uuid4()), "progress": 50, "lock_version": 1}]
        })
    assert response.status_code == status_code
    db.rollback.assert_called_once_with(); db.commit.assert_not_called()


def test_tracking_schema_rejects_planning_fields_and_auth_is_required(pending_routes) -> None:
    client, db, _user, _workspace = pending_routes
    response = client.patch("/api/v1/pending-items/tracking", json={
        "items": [{"id": str(uuid.uuid4()), "name": "Otro", "lock_version": 1}]
    })
    assert response.status_code == 422 and not db.commit.called

    app.dependency_overrides.clear()
    with TestClient(app) as anonymous:
        response = anonymous.get("/api/v1/pending-items")
    assert response.status_code == 401
