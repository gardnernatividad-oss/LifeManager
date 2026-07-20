from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import test_connection

print(f"Base de datos: {settings.DB_NAME}")

app = FastAPI(
    title="LifeManager API",
    description="Backend de LifeManager",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_router)


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
