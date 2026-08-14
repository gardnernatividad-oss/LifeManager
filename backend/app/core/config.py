from pydantic import Field, model_validator
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
    ALGORITHM: str = "HS256"
    SQL_ECHO: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    TASK_BULK_MAX_OCCURRENCES: int = 1000

    @model_validator(mode="after")
    def require_database_configuration(self) -> "Settings":
        if self.DATABASE_URL:
            return self
        if any(
            value is None
            for value in (
                self.DB_HOST,
                self.DB_PORT,
                self.DB_NAME,
                self.DB_USER,
                self.DB_PASSWORD,
            )
        ):
            raise ValueError(
                "Configure DATABASE_URL or all DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD values"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
