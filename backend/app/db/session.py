from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

DATABASE_URL = (
    f"postgresql+psycopg://"
    f"{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}"
    f"/{settings.DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    echo=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

from sqlalchemy import text


def test_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        return result.scalar()