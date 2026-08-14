from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

def _database_url() -> str:
    if settings.DATABASE_URL:
        if settings.DATABASE_URL.startswith("postgres://"):
            return settings.DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
        if settings.DATABASE_URL.startswith("postgresql://"):
            return settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
        return settings.DATABASE_URL
    return (
        f"postgresql+psycopg://"
        f"{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}"
        f"/{settings.DB_NAME}"
    )


DATABASE_URL = _database_url()

engine = create_engine(
    DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
