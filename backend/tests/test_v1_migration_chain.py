import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from tests.postgres_safety import alembic_config_for_test_database
from tests.postgres_safety import disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND_ROOT / "alembic" / "versions"


def _load_reset_migration():
    path = VERSIONS / "c2d3e4f5a6b7_reset_legacy_schema_for_v1.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrations_form_one_linear_v2_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["b9c0d1e2f3a4"]
    current = script.get_revision("d5e6f7a8b9c0")
    rate_limits = script.get_revision("c3d172b18308")
    v2_reset = script.get_revision("e4f5a6b7c8d9")
    target = script.get_revision("d3e4f5a6b7c8")
    reset = script.get_revision("c2d3e4f5a6b7")
    assert current is not None and current.down_revision == "c3d172b18308"
    assert rate_limits is not None and rate_limits.down_revision == "e4f5a6b7c8d9"
    assert v2_reset is not None and v2_reset.down_revision == "d3e4f5a6b7c8"
    assert target is not None and target.down_revision == "c2d3e4f5a6b7"
    assert reset is not None and reset.down_revision == "1b2c3d4e5f60"


def test_new_migration_modules_import() -> None:
    for filename in (
        "c2d3e4f5a6b7_reset_legacy_schema_for_v1.py",
        "d3e4f5a6b7c8_create_v1_target_domain.py",
    ):
        path = VERSIONS / filename
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def test_reset_migration_has_an_explicit_destructive_guard() -> None:
    source = (VERSIONS / "c2d3e4f5a6b7_reset_legacy_schema_for_v1.py").read_text(
        encoding="utf-8"
    )
    assert "LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET" in source
    assert "lifemanager_stage4_" in source
    assert "inet_server_addr" in source


def test_empty_bootstrap_requires_parent_revision_all_tables_and_no_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_reset_migration()
    bind = MagicMock()
    revision_result = bind.execute.return_value
    revision_result.scalars.return_value.all.return_value = [migration.down_revision]
    empty_result = MagicMock()
    empty_result.scalar_one.return_value = False
    bind.execute.side_effect = [revision_result] + [empty_result] * len(
        migration.LEGACY_TABLES
    )
    inspector = MagicMock()
    inspector.get_table_names.return_value = [*migration.LEGACY_TABLES, "alembic_version"]
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)

    assert migration._is_verified_empty_bootstrap_database(bind) is True


def test_data_bearing_database_is_not_an_automatic_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_reset_migration()
    bind = MagicMock()
    revision_result = MagicMock()
    revision_result.scalars.return_value.all.return_value = [migration.down_revision]
    populated_result = MagicMock()
    populated_result.scalar_one.return_value = True
    bind.execute.side_effect = [revision_result, populated_result]
    inspector = MagicMock()
    inspector.get_table_names.return_value = [*migration.LEGACY_TABLES, "alembic_version"]
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    monkeypatch.delenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET", raising=False)

    with pytest.raises(RuntimeError, match="Destructive V1 schema reset refused"):
        migration._require_explicit_development_database(bind)


def test_explicit_verified_local_development_reset_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_reset_migration()
    bind = MagicMock()
    revision_result = MagicMock()
    revision_result.scalars.return_value.all.return_value = ["legacy-test-revision"]
    database_result = MagicMock()
    database_result.one.return_value = ("lifemanager_stage4_test", "127.0.0.1/32")
    bind.execute.side_effect = [revision_result, database_result]
    monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET", "1")

    migration._require_explicit_development_database(bind)


def test_fresh_disposable_postgresql_database_upgrades_from_base_to_v2_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db import session as db_session

    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Disposable migration-chain test requires local PostgreSQL")

    database_name = "lifemanager_v2_test"
    with disposable_postgres_database(
        source_url,
        database_name=database_name,
        explicit_test_intent=True,
    ) as target_url:
        monkeypatch.delenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_SCHEMA_RESET", raising=False)
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        config = alembic_config_for_test_database(
            target_url,
            backend_root=BACKEND_ROOT,
            explicit_test_intent=True,
        )
        command.upgrade(config, "head")

        target_engine = sa.create_engine(target_url)
        with target_engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "b9c0d1e2f3a4"
            tables = set(sa.inspect(connection).get_table_names())
            assert {
                "users",
                "workspaces",
                "workspace_members",
                "workspace_invitations",
                "categories",
                "master_tasks",
                "tasks",
                "pending_items",
                "projects",
                "project_stages",
                "rate_limit_buckets",
            }.issubset(tables)
        target_engine.dispose()
        command.downgrade(config, "a8b9c0d1e2f3")
        command.upgrade(config, "head")
        roundtrip_engine = sa.create_engine(target_url)
        with roundtrip_engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "b9c0d1e2f3a4"
        roundtrip_engine.dispose()
