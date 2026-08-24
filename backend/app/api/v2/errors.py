from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(eq=False)
class V2APIError(Exception):
    status_code: int
    code: str
    message: str
    headers: dict[str, str] | None = None


def error_payload(*, code: str, message: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": None,
            "request_id": None,
        }
    }


async def v2_api_error_handler(
    _request: Request,
    error: V2APIError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=error_payload(code=error.code, message=error.message),
        headers=error.headers,
    )


async def v2_unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not request.url.path.startswith("/api/v2/"):
        raise error
    return JSONResponse(
        status_code=500,
        content=error_payload(
            code="INTERNAL_ERROR",
            message="Ocurrió un error inesperado.",
        ),
    )
