import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND_ROOT / "alembic" / "versions"


def test_v1_migrations_form_one_linear_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["d3e4f5a6b7c8"]
    target = script.get_revision("d3e4f5a6b7c8")
    reset = script.get_revision("c2d3e4f5a6b7")
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
