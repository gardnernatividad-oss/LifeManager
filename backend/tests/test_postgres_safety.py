from pathlib import Path

import pytest

from app.db import session as db_session
from tests.postgres_safety import (
    DISPOSABLE_TEST_DATABASES,
    UnsafeTestDatabaseError,
    alembic_config_for_test_database,
    disposable_postgres_database,
    inspect_test_database_target,
    require_disposable_test_database,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "database_name",
    sorted(DISPOSABLE_TEST_DATABASES),
)
def test_only_explicit_disposable_database_names_are_allowed(
    database_name: str,
) -> None:
    target = require_disposable_test_database(
        f"postgresql+psycopg://redacted@127.0.0.1/{database_name}",
        explicit_test_intent=True,
    )
    assert target.host_classification == "loopback"
    assert target.database_name == database_name
    assert target.allowlisted is True


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_shared_lifemanager_database_is_refused_before_any_connection(
    host: str,
) -> None:
    authority = f"[{host}]" if ":" in host else host
    target = inspect_test_database_target(
        f"postgresql+psycopg://redacted@{authority}/lifemanager"
    )
    assert target.host_classification == "loopback"
    assert target.allowlisted is False
    with pytest.raises(UnsafeTestDatabaseError, match="never a disposable"):
        require_disposable_test_database(
            target.url,
            explicit_test_intent=True,
        )


def test_loopback_alone_and_missing_intent_are_insufficient() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="allowlist"):
        require_disposable_test_database(
            "postgresql+psycopg://redacted@localhost/arbitrary",
            explicit_test_intent=True,
        )
    with pytest.raises(UnsafeTestDatabaseError, match="explicit test intent"):
        require_disposable_test_database(
            "postgresql+psycopg://redacted@localhost/lifemanager_v2_test",
            explicit_test_intent=False,
        )


def test_remote_or_neon_target_is_refused() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="loopback"):
        require_disposable_test_database(
            "postgresql+psycopg://redacted@ep-example.neon.tech/lifemanager_v2_test",
            explicit_test_intent=True,
        )


def test_explicit_alembic_target_wins_over_cached_application_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached_shared_url = (
        "postgresql+psycopg://redacted@localhost/lifemanager"
    )
    intended_url = (
        "postgresql+psycopg://redacted@localhost/lifemanager_v2_test"
    )
    monkeypatch.setattr(db_session, "DATABASE_URL", cached_shared_url)

    config = alembic_config_for_test_database(
        intended_url,
        backend_root=BACKEND_ROOT,
        explicit_test_intent=True,
    )

    assert config.attributes["database_url"] == intended_url
    assert config.attributes["database_url"] != db_session.DATABASE_URL


def test_alembic_env_prefers_explicit_config_target() -> None:
    source = (BACKEND_ROOT / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    assert 'config.attributes.get("database_url", db_session.DATABASE_URL)' in source


def test_disposable_lifecycle_refuses_shared_target_before_engine_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_engine = __import__("unittest.mock").mock.MagicMock()
    monkeypatch.setattr("tests.postgres_safety.sa.create_engine", create_engine)

    with pytest.raises(UnsafeTestDatabaseError, match="never a disposable"):
        with disposable_postgres_database(
            "postgresql+psycopg://redacted@localhost/lifemanager",
            database_name="lifemanager",
            explicit_test_intent=True,
        ):
            pass

    create_engine.assert_not_called()
