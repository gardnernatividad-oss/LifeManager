import hmac

from collections.abc import Awaitable, Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v2.errors import V2APIError, v2_api_error_handler
from app.core.config import settings
from app.core.session_security import csrf_matches_session, decode_session_token


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_UNAUTHENTICATED_PATHS = {
    "/api/v2/auth/registration-requests",
    "/api/v2/auth/email-verifications",
    "/api/v2/auth/email-verifications/resend",
    "/api/v2/auth/password-recovery-requests",
    "/api/v2/auth/password-resets",
    "/api/v2/auth/login",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            request.method in SAFE_METHODS
            or request.url.path in PUBLIC_UNAUTHENTICATED_PATHS
            or settings.SESSION_COOKIE_NAME not in request.cookies
        ):
            return await call_next(request)

        origin = request.headers.get("Origin")
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(settings.CSRF_HEADER_NAME)
        claims = decode_session_token(request.cookies.get(settings.SESSION_COOKIE_NAME))
        if (
            origin not in settings.CORS_ALLOWED_ORIGINS
            or not csrf_cookie
            or not csrf_header
            or not hmac.compare_digest(csrf_cookie, csrf_header)
            or claims is None
            or not csrf_matches_session(claims, csrf_cookie)
        ):
            return await v2_api_error_handler(
                request,
                V2APIError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="CSRF_VALIDATION_FAILED",
                    message="No se pudo validar la solicitud.",
                ),
            )
        return await call_next(request)
