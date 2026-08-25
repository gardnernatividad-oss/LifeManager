import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db, require_active_workspace_membership
from app.main import app
from app.models import Category, MasterTask


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
WORKSPACE_ID = uuid.uuid4()


def _client(db: MagicMock) -> TestClient:
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[require_active_workspace_membership] = lambda: SimpleNamespace()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _category() -> Category:
    return Category(id=uuid.uuid4(), workspace_id=WORKSPACE_ID, name="Personal", normalized_name="personal", is_active=True, lock_version=1, created_at=NOW, updated_at=NOW)


def test_category_create_is_workspace_scoped_and_route_owns_transaction() -> None:
    db = MagicMock()
    category = _category()
    with patch("app.api.v2.catalogs.create_category", return_value=category) as service, _client(db) as client:
        response = client.post(f"/api/v2/workspaces/{WORKSPACE_ID}/categories", json={"name": " Personal "})
    assert response.status_code == 201
    assert response.json()["workspace_id"] == str(WORKSPACE_ID)
    service.assert_called_once()
    assert service.call_args.kwargs["workspace_id"] == WORKSPACE_ID
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(category)


def test_foreign_or_missing_catalog_is_safely_masked() -> None:
    db = MagicMock()
    from app.services.v2_catalog import CatalogNotFoundError
    with patch("app.api.v2.catalogs.get_category", side_effect=CatalogNotFoundError), _client(db) as client:
        response = client.get(f"/api/v2/workspaces/{WORKSPACE_ID}/categories/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CATALOG_NOT_FOUND"


def test_master_task_response_is_explicit_and_hides_normalized_name() -> None:
    db = MagicMock()
    category = _category()
    item = MasterTask(id=uuid.uuid4(), workspace_id=WORKSPACE_ID, category_id=category.id, name="Leer", normalized_name="leer", is_active=True, lock_version=2, created_at=NOW, updated_at=NOW)
    item.category = category
    with patch("app.api.v2.catalogs.get_item", return_value=item), _client(db) as client:
        response = client.get(f"/api/v2/workspaces/{WORKSPACE_ID}/master-tasks/{item.id}")
    assert response.status_code == 200
    assert response.json()["category_name"] == "Personal"
    assert "normalized_name" not in response.json()
    db.commit.assert_not_called()


def test_catalog_mass_assignment_is_rejected() -> None:
    db = MagicMock()
    with _client(db) as client:
        response = client.post(f"/api/v2/workspaces/{WORKSPACE_ID}/categories", json={"name": "Casa", "workspace_id": str(uuid.uuid4()), "is_active": False})
    assert response.status_code == 422


def test_catalog_openapi_has_safe_delete_and_selectors_for_all_resources() -> None:
    paths = app.openapi()["paths"]
    for resource in ("categories", "master-tasks", "activity-masters"):
        path = f"/api/v2/workspaces/{{workspace_id}}/{resource}"
        assert {"get", "post"} <= set(paths[path])
        item_parameter = "category_id" if resource == "categories" else "item_id"
        assert "delete" in paths[f"{path}/{{{item_parameter}}}"]
    for selector in ("categories", "tasks", "activities"):
        assert "get" in paths[f"/api/v2/workspaces/{{workspace_id}}/selectors/{selector}"]


def test_referenced_delete_maps_to_conflict_and_rolls_back() -> None:
    db = MagicMock()
    from app.services.v2_catalog import CatalogReferencedError
    with patch("app.api.v2.catalogs.delete_category", side_effect=CatalogReferencedError), _client(db) as client:
        response = client.delete(f"/api/v2/workspaces/{WORKSPACE_ID}/categories/{uuid.uuid4()}?lock_version=1")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CATALOG_REFERENCED"
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_selector_is_workspace_scoped_and_returns_minimal_projection() -> None:
    db = MagicMock()
    category = _category()
    with patch("app.api.v2.catalogs.category_selector", return_value=[category]) as service, _client(db) as client:
        response = client.get(f"/api/v2/workspaces/{WORKSPACE_ID}/selectors/categories")
    assert response.status_code == 200
    assert response.json() == [{"id": str(category.id), "name": "Personal", "is_active": True, "category_id": None, "category_name": None}]
    assert service.call_args.kwargs["workspace_id"] == WORKSPACE_ID
    db.commit.assert_not_called()
