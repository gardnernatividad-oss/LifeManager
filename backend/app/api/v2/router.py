from fastapi import APIRouter

from app.api.v2.identity import router as identity_router
from app.api.v2.workspaces import router as workspace_router


api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(workspace_router)
