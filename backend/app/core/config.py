from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: Literal["HS256"] = "HS256"
    SQL_ECHO: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    SESSION_COOKIE_NAME: str = "lifemanager_v2_session"
    CSRF_COOKIE_NAME: str = "lifemanager_v2_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    SESSION_EXPIRE_MINUTES: int = 480
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_COOKIE_SECURE: bool | None = None
    RATE_LIMIT_HMAC_KEY: str | None = Field(default=None, min_length=32)
    RATE_LIMIT_TRUSTED_PROXY_CIDRS: list[str] = Field(default_factory=list)
    RATE_LIMIT_FORWARDED_HEADER: Literal[
        "x-forwarded-for", "x-real-ip", "cf-connecting-ip"
    ] = "x-forwarded-for"
    TURNSTILE_ENABLED: bool = False
    TURNSTILE_SECRET_KEY: str | None = Field(default=None, min_length=1)
    TURNSTILE_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0, le=10.0)
    TASK_BULK_MAX_OCCURRENCES: int = 1000

    @field_validator("RATE_LIMIT_TRUSTED_PROXY_CIDRS")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, values: list[str]) -> list[str]:
        from ipaddress import ip_network

        for value in values:
            ip_network(value, strict=False)
        return values

    @model_validator(mode="after")
    def require_database_configuration(self) -> "Settings":
        if "*" in self.CORS_ALLOWED_ORIGINS:
            raise ValueError("Credentialed CORS requires explicit origins")
        if self.DATABASE_URL:
            configured = True
        else:
            configured = not any(
                value is None
                for value in (
                    self.DB_HOST,
                    self.DB_PORT,
                    self.DB_NAME,
                    self.DB_USER,
                    self.DB_PASSWORD,
                )
            )
        if not configured:
            raise ValueError(
                "Configure DATABASE_URL or all DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD values"
            )
        if self.SESSION_COOKIE_SAMESITE == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires a Secure session cookie")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if self.database_host not in local_hosts and not self.session_cookie_secure:
            raise ValueError("Remote database configuration requires Secure session cookies")
        if self.database_host not in local_hosts and not self.TURNSTILE_ENABLED:
            raise ValueError("Turnstile must be enabled for secure production configuration")
        if self.TURNSTILE_ENABLED and not self.TURNSTILE_SECRET_KEY:
            raise ValueError("TURNSTILE_SECRET_KEY is required when Turnstile is enabled")
        return self

    @property
    def database_host(self) -> str:
        if self.DATABASE_URL:
            host = urlparse(
                self.DATABASE_URL.replace("postgresql+psycopg", "postgresql", 1)
            ).hostname
        else:
            host = self.DB_HOST
        return (host or "").lower()

    @property
    def session_cookie_secure(self) -> bool:
        if self.SESSION_COOKIE_SECURE is not None:
            return self.SESSION_COOKIE_SECURE
        return self.database_host not in {"localhost", "127.0.0.1", "::1"}

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
