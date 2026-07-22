from fastapi import APIRouter

from app.api.v1.categories import router as categories_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.daily_form import router as daily_form_router
from app.api.v1.daily_task_generation import router as daily_task_generation_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.task_series import router as task_series_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(workspaces_router)
api_router.include_router(dashboard_router)
api_router.include_router(daily_form_router)
api_router.include_router(daily_task_generation_router)
api_router.include_router(tasks_router)
api_router.include_router(categories_router)
api_router.include_router(projects_router)
api_router.include_router(task_series_router)
