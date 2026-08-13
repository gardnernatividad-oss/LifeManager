from fastapi.testclient import TestClient

from app.main import app
from app.models import Task
from app.schemas.task import TaskBulkCreate, TaskCreate, TaskRead, TaskUpdate


LEGACY_ROUTE_TERMS = {
    "task-series",
    "daily-form",
    "daily-workflow",
    "reminder",
    "user-settings",
    "workspace-settings",
    "dashboard",
    "members",
    "invitations",
}

REQUIRED_V1_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/me",
    "/api/v1/timezones",
    "/api/v1/categories",
    "/api/v1/categories/{category_id}",
    "/api/v1/master-tasks",
    "/api/v1/master-tasks/{master_task_id}",
    "/api/v1/tasks",
    "/api/v1/tasks/bulk",
    "/api/v1/tasks/bulk-delete",
    "/api/v1/tasks/{task_id}",
    "/api/v1/tasks/{task_id}/result",
    "/api/v1/pending-items",
    "/api/v1/pending-items/tracking",
    "/api/v1/pending-items/{pending_item_id}",
    "/api/v1/projects",
    "/api/v1/projects/{project_id}",
    "/api/v1/projects/{project_id}/steps",
    "/api/v1/projects/{project_id}/steps/{step_id}",
    "/api/v1/projects/{project_id}/tracking",
    "/api/v1/projects/{project_id}/tracking-general",
    "/api/v1/review",
    "/api/v1/home",
    "/api/v1/reports/tasks",
    "/api/v1/reports/pending-items",
    "/api/v1/reports/projects",
}

LEGACY_SCHEMA_TERMS = {
    "TaskSeries",
    "DailyForm",
    "DailyWorkflow",
    "Reminder",
    "UserSettings",
    "WorkspaceSettings",
    "Dashboard",
}

LEGACY_TASK_FIELDS = {
    "title",
    "description",
    "scheduled_at",
    "due_at",
    "priority",
    "category_id",
    "project_id",
    "task_series_id",
}


def test_openapi_exposes_target_v1_routes_without_legacy_runtime() -> None:
    with TestClient(app) as client:
        openapi = client.get("/openapi.json").json()
    paths = set(openapi["paths"])
    assert REQUIRED_V1_PATHS <= paths
    assert "/auth/login" not in paths
    assert "/auth/register" not in paths
    assert "/auth/me" not in paths
    assert "/db" not in paths
    assert not any(
        term in path.lower() for path in paths for term in LEGACY_ROUTE_TERMS
    )
    password_flow = openapi["components"]["securitySchemes"]["OAuth2PasswordBearer"][
        "flows"
    ]["password"]
    assert password_flow["tokenUrl"] == "/api/v1/auth/login"


def test_openapi_does_not_publish_legacy_schemas_or_task_fields() -> None:
    with TestClient(app) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert not any(
        term in schema_name
        for schema_name in schemas
        for term in LEGACY_SCHEMA_TERMS
    )
    for schema_name in ("TaskCreate", "TaskUpdate", "TaskBulkCreate"):
        properties = set(schemas[schema_name]["properties"])
        assert LEGACY_TASK_FIELDS.isdisjoint(properties)
    assert "CANCELLED" not in str(schemas)
    assert "week_starts_on" not in str(schemas)


def test_runtime_task_contract_and_metadata_have_no_legacy_fields() -> None:
    assert LEGACY_TASK_FIELDS.isdisjoint(Task.__table__.columns.keys())
    for schema in (TaskCreate, TaskUpdate, TaskBulkCreate, TaskRead):
        assert LEGACY_TASK_FIELDS.isdisjoint(schema.model_fields)
