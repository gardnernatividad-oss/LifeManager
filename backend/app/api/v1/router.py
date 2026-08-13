from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.master_tasks import router as master_tasks_router
from app.api.v1.pending_items import router as pending_items_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(master_tasks_router)
api_router.include_router(pending_items_router)
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
