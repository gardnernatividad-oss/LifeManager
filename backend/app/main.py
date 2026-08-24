from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware

from app.api.v2.errors import (
    V2APIError,
    error_payload,
    v2_api_error_handler,
    v2_unexpected_error_handler,
)
from app.api.v2.csrf import CSRFMiddleware
from app.api.v2.router import api_router
from app.core.config import settings

app = FastAPI(
    title="LifeManager API",
    description="Backend de LifeManager",
    version="0.1.0",
)

app.add_middleware(CSRFMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        settings.CSRF_HEADER_NAME,
    ],
)

app.add_exception_handler(V2APIError, v2_api_error_handler)
app.add_exception_handler(Exception, v2_unexpected_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    error: RequestValidationError,
):
    if not request.url.path.startswith("/api/v2/"):
        return await request_validation_exception_handler(request, error)
    details = [
        {
            "field": ".".join(str(part) for part in item["loc"] if part != "body"),
            "code": item["type"],
            "message": item["msg"],
        }
        for item in error.errors()
    ]
    payload = error_payload(
        code="VALIDATION_ERROR",
        message="La solicitud contiene datos inválidos.",
    )
    payload["error"]["details"] = details
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content=payload)


app.include_router(api_router, prefix="/api/v2")


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
