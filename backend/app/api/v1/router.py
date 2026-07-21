from fastapi import APIRouter

from app.api.v1.categories import router as categories_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(workspaces_router)
api_router.include_router(tasks_router)
api_router.include_router(categories_router)
