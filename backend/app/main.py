from fastapi import FastAPI
from app.core.config import settings
from app.db.session import test_connection

print(f"Base de datos: {settings.DB_NAME}")

app = FastAPI(
    title="LifeManager API",
    description="Backend de LifeManager",
    version="0.1.0",
)


@app.get("/", tags=["General"])
def root():
    return {
        "application": "LifeManager",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health", tags=["General"])
def health_check():
    return {
        "status": "healthy"
    }


@app.get("/db", tags=["General"])
def database_test():
    return {
        "database": test_connection()
    }