from fastapi import APIRouter

from app.api.v2.identity import router as identity_router


api_router = APIRouter()
api_router.include_router(identity_router)
