import pytest

from pydantic import ValidationError

from app.core.config import Settings
from app.db import session


SECRET = "production-test-secret-with-at-least-32-characters"


def test_production_database_url_and_safe_sql_logging_default() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:password@db.example/lifemanager",
        SECRET_KEY=SECRET,
    )

    assert settings.DATABASE_URL == "postgresql://user:password@db.example/lifemanager"
    assert settings.SQL_ECHO is False
    assert settings.session_cookie_secure is True


def test_component_database_configuration_remains_supported() -> None:
    settings = Settings(
        _env_file=None,
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="lifemanager",
        DB_USER="postgres",
        DB_PASSWORD="password",
        SECRET_KEY=SECRET,
    )

    assert settings.DB_HOST == "localhost"
    assert settings.session_cookie_secure is False


def test_cookie_cross_site_and_credentialed_cors_require_safe_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:password@db.example/lifemanager",
            SECRET_KEY=SECRET,
            CORS_ALLOWED_ORIGINS=["*"],
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_NAME="lifemanager",
            DB_USER="postgres",
            DB_PASSWORD="password",
            SECRET_KEY=SECRET,
            SESSION_COOKIE_SAMESITE="none",
        )


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_provider_database_urls_use_the_installed_psycopg_driver(
    monkeypatch: pytest.MonkeyPatch,
    scheme: str,
) -> None:
    monkeypatch.setattr(
        session.settings,
        "DATABASE_URL",
        f"{scheme}user:password@db.example/lifemanager",
    )

    assert session._database_url().startswith("postgresql+psycopg://")


def test_missing_database_or_short_secret_fails_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=SECRET)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:password@db.example/lifemanager",
            SECRET_KEY="too-short",
        )


def test_rate_limit_security_configuration_is_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:password@db.example/lifemanager",
            SECRET_KEY=SECRET,
            RATE_LIMIT_HMAC_KEY="too-short",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://user:password@db.example/lifemanager",
            SECRET_KEY=SECRET,
            RATE_LIMIT_TRUSTED_PROXY_CIDRS=["not-a-network"],
        )
