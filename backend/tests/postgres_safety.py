from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import URL, make_url


LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DISPOSABLE_TEST_DATABASES = frozenset(
    {"lifemanager_test", "lifemanager_v2_test"}
)
SHARED_LOCAL_DATABASE = "lifemanager"


class UnsafeTestDatabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class TestDatabaseTarget:
    url: URL
    host_classification: str
    database_name: str
    allowlisted: bool


def inspect_test_database_target(database_url: str | URL) -> TestDatabaseTarget:
    url = make_url(database_url)
    host = (url.host or "").lower()
    database_name = url.database or ""
    return TestDatabaseTarget(
        url=url,
        host_classification="loopback" if host in LOCAL_DATABASE_HOSTS else "non-local",
        database_name=database_name,
        allowlisted=database_name in DISPOSABLE_TEST_DATABASES,
    )


def require_disposable_test_database(
    database_url: str | URL,
    *,
    explicit_test_intent: bool,
) -> TestDatabaseTarget:
    target = inspect_test_database_target(database_url)
    if not explicit_test_intent:
        raise UnsafeTestDatabaseError(
            "Disposable PostgreSQL operation requires explicit test intent"
        )
    if target.host_classification != "loopback":
        raise UnsafeTestDatabaseError(
            "Disposable PostgreSQL operation requires a loopback host"
        )
    if target.database_name == SHARED_LOCAL_DATABASE:
        raise UnsafeTestDatabaseError(
            "Shared local database is never a disposable test target"
        )
    if not target.allowlisted:
        raise UnsafeTestDatabaseError(
            "Database name is not in the disposable-test allowlist"
        )
    return target


def alembic_config_for_test_database(
    database_url: str | URL,
    *,
    backend_root: Path,
    explicit_test_intent: bool,
) -> Config:
    target = require_disposable_test_database(
        database_url,
        explicit_test_intent=explicit_test_intent,
    )
    config = Config(str(backend_root / "alembic.ini"))
    config.attributes["database_url"] = target.url.render_as_string(
        hide_password=False
    )
    return config


@contextmanager
def disposable_postgres_database(
    source_url: str | URL,
    *,
    database_name: str,
    explicit_test_intent: bool,
) -> Iterator[URL]:
    source = make_url(source_url)
    target = require_disposable_test_database(
        source.set(database=database_name),
        explicit_test_intent=explicit_test_intent,
    )
    admin_engine = sa.create_engine(
        source.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                sa.text("SELECT 1 FROM pg_database WHERE datname=:name"),
                {"name": target.database_name},
            )
            if exists:
                raise UnsafeTestDatabaseError(
                    "Disposable test database already exists; refusing ambiguous reuse"
                )
            connection.exec_driver_sql(
                f'CREATE DATABASE "{target.database_name}"'
            )
        try:
            yield target.url
        finally:
            with admin_engine.connect() as connection:
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname=:name AND pid <> pg_backend_pid()"
                    ),
                    {"name": target.database_name},
                )
                connection.exec_driver_sql(
                    f'DROP DATABASE "{target.database_name}"'
                )
    finally:
        admin_engine.dispose()
