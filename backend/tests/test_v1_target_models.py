from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models import (
    Category,
    MasterTask,
    PendingItem,
    Project,
    ProjectStep,
    Task,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceTrackingMetadata,
)
from app.models.base import Base


TARGET_TABLES = {
    "users",
    "workspaces",
    "workspace_members",
    "workspace_tracking_metadata",
    "categories",
    "master_tasks",
    "tasks",
    "pending_items",
    "projects",
    "project_steps",
}


def _named(items: set[object], type_: type[object]) -> set[str]:
    return {
        item.name for item in items if isinstance(item, type_) and item.name is not None
    }


def test_target_metadata_contains_exactly_the_approved_tables() -> None:
    assert set(Base.metadata.tables) == TARGET_TABLES
    configure_mappers()


def test_task_is_date_only_and_contains_no_legacy_domain_columns() -> None:
    columns = Task.__table__.columns
    assert columns.planned_date.type.__class__.__name__ == "Date"
    assert {
        "title",
        "description",
        "scheduled_at",
        "category_id",
        "project_id",
        "task_series_id",
        "status",
        "priority",
    }.isdisjoint(columns.keys())
    assert columns.result.nullable is True
    assert str(columns.lock_version.server_default.arg) == "1"


def test_workspace_aware_constraints_and_target_indexes_exist() -> None:
    category_constraints = set(Category.__table__.constraints)
    master_constraints = set(MasterTask.__table__.constraints)
    task_constraints = set(Task.__table__.constraints)

    assert "uq_categories_id_workspace_id" in _named(category_constraints, UniqueConstraint)
    assert "fk_master_tasks_category_workspace" in _named(master_constraints, ForeignKeyConstraint)
    assert "fk_tasks_master_task_workspace" in _named(task_constraints, ForeignKeyConstraint)
    assert "uq_tasks_workspace_id_master_task_id_planned_date" in _named(
        task_constraints, UniqueConstraint
    )
    assert "ix_tasks_workspace_id_planned_date_id" in _named(set(Task.__table__.indexes), Index)


def test_target_defaults_and_checks_exist() -> None:
    for model in (Task, PendingItem, Project, ProjectStep):
        assert str(model.__table__.columns.lock_version.server_default.arg) == "1"
        checks = _named(set(model.__table__.constraints), CheckConstraint)
        assert any("lock_version" in name for name in checks)

    assert str(PendingItem.__table__.columns.progress.server_default.arg) == "0"
    assert str(ProjectStep.__table__.columns.progress.server_default.arg) == "0"
    assert str(Workspace.__table__.columns.kind.server_default.arg) == "'PERSONAL'"


def test_tracking_metadata_is_a_workspace_one_to_one_primary_key() -> None:
    table = WorkspaceTrackingMetadata.__table__
    assert list(table.primary_key.columns.keys()) == ["workspace_id"]
    foreign_key = next(iter(table.columns.workspace_id.foreign_keys))
    assert foreign_key.target_fullname == "workspaces.id"
    assert foreign_key.ondelete == "CASCADE"


def test_all_target_models_are_registered() -> None:
    assert {
        User.__tablename__,
        Workspace.__tablename__,
        WorkspaceMember.__tablename__,
        WorkspaceTrackingMetadata.__tablename__,
        Category.__tablename__,
        MasterTask.__tablename__,
        Task.__tablename__,
        PendingItem.__tablename__,
        Project.__tablename__,
        ProjectStep.__tablename__,
    } == TARGET_TABLES
