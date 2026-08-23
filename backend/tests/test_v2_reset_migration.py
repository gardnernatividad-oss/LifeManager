import importlib.util
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "e4f5a6b7c8d9_reset_v1_and_create_v2_schema.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("v2_reset_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reset_revision_and_allowlist_are_explicit() -> None:
    migration = _migration()
    assert migration.revision == "e4f5a6b7c8d9"
    assert migration.down_revision == "d3e4f5a6b7c8"
    assert set(migration.V1_DROP_ORDER) == migration.V1_TABLES
    assert "alembic_version" not in migration.V1_TABLES


def test_reset_refuses_before_inspection_without_opt_in(monkeypatch) -> None:
    migration = _migration()
    monkeypatch.delenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", raising=False)
    with pytest.raises(RuntimeError, match="LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET"):
        migration._assert_safe_target(None)


def test_any_safety_refusal_precedes_all_destructive_ddl(monkeypatch) -> None:
    migration = _migration()
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(
        migration,
        "_assert_safe_target",
        MagicMock(side_effect=RuntimeError("safety refusal")),
    )
    drop_table = MagicMock()
    execute = MagicMock()
    monkeypatch.setattr(migration.op, "drop_table", drop_table)
    monkeypatch.setattr(migration.op, "execute", execute)

    with pytest.raises(RuntimeError, match="safety refusal"):
        migration.upgrade()

    drop_table.assert_not_called()
    execute.assert_not_called()


def test_downgrade_is_explicitly_irreversible() -> None:
    with pytest.raises(RuntimeError, match="irreversible"):
        _migration().downgrade()


def test_revision_is_independent_from_live_application_metadata() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(module.startswith("app.models") for module in imported_modules)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_all"
        for node in ast.walk(tree)
    )
    frozen_tables = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__tablename__" for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    assert len(frozen_tables) == 25


def test_nonlocal_target_is_refused_before_database_inspection(monkeypatch) -> None:
    migration = _migration()
    monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
    monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
    bind = SimpleNamespace(engine=SimpleNamespace(url=__import__("sqlalchemy").engine.make_url(
        "postgresql+psycopg://redacted@remote.example/lifemanager_test"
    )))
    with pytest.raises(RuntimeError, match="not loopback/local"):
        migration._assert_safe_target(bind)


def test_unexpected_v1_object_is_refused_before_destructive_ddl(monkeypatch) -> None:
    migration = _migration()
    monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
    monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
    monkeypatch.setenv("LIFEMANAGER_DESTRUCTIVE_DB_ALLOWLIST", "lifemanager_v2_test")

    class Result:
        def scalar_one(self):
            return migration.down_revision

    bind = SimpleNamespace(
        engine=SimpleNamespace(url=__import__("sqlalchemy").engine.make_url(
            "postgresql+psycopg://redacted@127.0.0.1/lifemanager_v2_test"
        )),
        execute=lambda statement: Result(),
    )
    inspector = SimpleNamespace(
        get_table_names=lambda schema: list(migration.V1_TABLES | {"unexpected_table"})
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda target: inspector)
    with pytest.raises(RuntimeError, match="table set"):
        migration._assert_safe_target(bind)


def test_nonallowlisted_database_is_refused_before_inspection(monkeypatch) -> None:
    migration = _migration()
    monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
    monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
    monkeypatch.delenv("LIFEMANAGER_DESTRUCTIVE_DB_ALLOWLIST", raising=False)
    bind = SimpleNamespace(engine=SimpleNamespace(url=__import__("sqlalchemy").engine.make_url(
        "postgresql+psycopg://redacted@127.0.0.1/not_allowlisted"
    )))
    with pytest.raises(RuntimeError, match="not explicitly allowlisted"):
        migration._assert_safe_target(bind)


@pytest.mark.parametrize("schema_defect", ["columns", "enum_types"])
def test_unexpected_v1_shape_is_refused_before_destructive_ddl(
    monkeypatch, schema_defect: str,
) -> None:
    migration = _migration()
    monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
    monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
    monkeypatch.setenv("LIFEMANAGER_DESTRUCTIVE_DB_ALLOWLIST", "lifemanager_v2_test")

    class RevisionResult:
        def scalar_one(self):
            return migration.down_revision

    class EnumResult:
        def scalars(self):
            values = {"unexpected_type"} if schema_defect == "enum_types" else {"workspacerole"}
            return values

    execute_count = 0

    def execute(statement):
        nonlocal execute_count
        execute_count += 1
        return RevisionResult() if execute_count == 1 else EnumResult()

    bind = SimpleNamespace(
        engine=SimpleNamespace(url=__import__("sqlalchemy").engine.make_url(
            "postgresql+psycopg://redacted@127.0.0.1/lifemanager_v2_test"
        )),
        execute=execute,
    )
    inspector = SimpleNamespace(
        get_table_names=lambda schema: list(migration.V1_TABLES),
        get_columns=lambda table, schema: [
            {"name": column}
            for column in (
                set(migration.SENTINEL_COLUMNS[table]) - ({next(iter(migration.SENTINEL_COLUMNS[table]))} if schema_defect == "columns" else set())
            )
        ],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda target: inspector)

    expected = "sentinel columns" if schema_defect == "columns" else "enum-type set"
    with pytest.raises(RuntimeError, match=expected):
        migration._assert_safe_target(bind)
