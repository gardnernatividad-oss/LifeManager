import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_personal_workspace
from app.main import app
from app.models import Category, MasterTask, Workspace, WorkspaceKind
from app.services.category_service import (
    CategoryInUseError,
    CategoryNameConflictError,
    CategoryNotFoundError,
)
from app.services.master_task_service import (
    MasterTaskCategoryNotFoundError,
    MasterTaskInUseError,
    MasterTaskNameConflictError,
    MasterTaskNotFoundError,
)


@pytest.fixture
def route_context():
    db = MagicMock(spec=Session)
    workspace = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_personal_workspace] = lambda: workspace
    with TestClient(app) as client:
        yield client, db, workspace
    app.dependency_overrides.clear()


def _category(workspace_id: uuid.UUID) -> Category:
    timestamp = datetime.now(timezone.utc)
    return Category(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name="Trabajo",
        normalized_name="trabajo",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _master_task(workspace_id: uuid.UUID, category: Category) -> MasterTask:
    timestamp = datetime.now(timezone.utc)
    return MasterTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name="Revisar agenda",
        normalized_name="revisar agenda",
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_category_create_uses_personal_workspace_and_commits(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    with patch("app.api.v1.categories.category_service.create_category", return_value=category) as service:
        response = client.post("/api/v1/categories", json={"name": " Trabajo "})
    assert response.status_code == 201
    assert response.json()["name"] == "Trabajo"
    assert "normalized_name" not in response.json()
    assert "workspace_id" not in response.json()
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_category_list_has_pagination_metadata_and_is_read_only(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    with patch("app.api.v1.categories.category_service.list_categories", return_value=([category], 26)):
        response = client.get("/api/v1/categories?page=2&page_size=25")
    assert response.status_code == 200
    assert response.json()["total_pages"] == 2
    assert response.json()["page"] == 2
    db.commit.assert_not_called()
    db.flush.assert_not_called()
    db.rollback.assert_not_called()


def test_category_update_and_delete_own_transactions(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    with patch("app.api.v1.categories.category_service.update_category", return_value=category):
        update_response = client.patch(
            f"/api/v1/categories/{category.id}", json={"name": "Trabajo"}
        )
    assert update_response.status_code == 200
    db.commit.assert_called_once_with()
    db.reset_mock()
    with patch("app.api.v1.categories.category_service.delete_category"):
        delete_response = client.delete(f"/api/v1/categories/{category.id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    db.commit.assert_called_once_with()


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (CategoryNameConflictError("duplicate"), "Category name already exists"),
        (CategoryInUseError("used"), "Category is already in use"),
    ],
)
def test_category_conflicts_return_409_and_rollback(route_context, error, detail) -> None:
    client, db, _workspace = route_context
    with patch("app.api.v1.categories.category_service.create_category", side_effect=error):
        response = client.post("/api/v1/categories", json={"name": "Trabajo"})
    assert response.status_code == 409
    assert response.json() == {"detail": detail}
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_missing_category_returns_404_and_rolls_back(route_context) -> None:
    client, db, _workspace = route_context
    with patch(
        "app.api.v1.categories.category_service.update_category",
        side_effect=CategoryNotFoundError("missing"),
    ):
        response = client.patch(
            f"/api/v1/categories/{uuid.uuid4()}", json={"name": "Trabajo"}
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}
    db.rollback.assert_called_once_with()


def test_master_task_create_returns_category_summary_and_commits(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    master_task = _master_task(workspace.id, category)
    with patch(
        "app.api.v1.master_tasks.master_task_service.create_master_task",
        return_value=master_task,
    ) as service:
        response = client.post(
            "/api/v1/master-tasks",
            json={"name": "Revisar agenda", "category_id": str(category.id)},
        )
    assert response.status_code == 201
    assert response.json()["category"] == {
        "id": str(category.id),
        "name": category.name,
        "created_at": category.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": category.updated_at.isoformat().replace("+00:00", "Z"),
    }
    assert "normalized_name" not in response.text
    assert service.call_args.kwargs["workspace_id"] == workspace.id
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(master_task)


def test_master_task_list_forwards_category_filter_and_paginates(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    master_task = _master_task(workspace.id, category)
    with patch(
        "app.api.v1.master_tasks.master_task_service.list_master_tasks",
        return_value=([master_task], 1),
    ) as service:
        response = client.get(
            f"/api/v1/master-tasks?category_id={category.id}&page=1&page_size=25"
        )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert service.call_args.kwargs["category_id"] == category.id
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_master_task_update_and_delete_commit_once(route_context) -> None:
    client, db, workspace = route_context
    category = _category(workspace.id)
    master_task = _master_task(workspace.id, category)
    with patch(
        "app.api.v1.master_tasks.master_task_service.update_master_task",
        return_value=master_task,
    ):
        response = client.patch(
            f"/api/v1/master-tasks/{master_task.id}", json={"name": "Revisar agenda"}
        )
    assert response.status_code == 200
    db.commit.assert_called_once_with()
    db.reset_mock()
    with patch("app.api.v1.master_tasks.master_task_service.delete_master_task"):
        response = client.delete(f"/api/v1/master-tasks/{master_task.id}")
    assert response.status_code == 204
    assert response.content == b""
    db.commit.assert_called_once_with()


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (MasterTaskCategoryNotFoundError("missing"), 404),
        (MasterTaskNameConflictError("duplicate"), 409),
    ],
)
def test_master_task_domain_errors_map_safely_and_rollback(
    route_context, error, status_code
) -> None:
    client, db, _workspace = route_context
    with patch(
        "app.api.v1.master_tasks.master_task_service.create_master_task", side_effect=error
    ):
        response = client.post(
            "/api/v1/master-tasks",
            json={"name": "Leer", "category_id": str(uuid.uuid4())},
        )
    assert response.status_code == status_code
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_used_master_task_update_returns_conflict_and_rolls_back(route_context) -> None:
    client, db, _workspace = route_context
    with patch(
        "app.api.v1.master_tasks.master_task_service.update_master_task",
        side_effect=MasterTaskInUseError("used"),
    ):
        response = client.patch(
            f"/api/v1/master-tasks/{uuid.uuid4()}", json={"name": "Nuevo"}
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "Master task is already in use"}
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_missing_master_task_returns_404_and_rolls_back(route_context) -> None:
    client, db, _workspace = route_context
    with patch(
        "app.api.v1.master_tasks.master_task_service.update_master_task",
        side_effect=MasterTaskNotFoundError("missing"),
    ):
        response = client.patch(
            f"/api/v1/master-tasks/{uuid.uuid4()}", json={"name": "Nuevo"}
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Master task not found"}
    db.rollback.assert_called_once_with()


def test_master_table_routes_require_authentication() -> None:
    db = MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/v1/categories").status_code == 401
        assert client.get("/api/v1/master-tasks").status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    ["/api/v1/categories?page=0", "/api/v1/master-tasks?page_size=101"],
)
def test_master_table_pagination_validation_returns_422(route_context, path: str) -> None:
    client, _db, _workspace = route_context
    assert client.get(path).status_code == 422
