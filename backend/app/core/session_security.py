import hashlib
import hmac
import secrets
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


MAX_SESSION_TOKEN_LENGTH = 4096


@dataclass(frozen=True)
class SessionClaims:
    user_id: uuid.UUID
    credential_version: str
    csrf_digest: str


def credential_version(hashed_password: str, status_changed_at: datetime) -> str:
    state_version = status_changed_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"credential:{hashed_password}:{state_version}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _csrf_digest(csrf_token: str, version: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"csrf:{version}:{csrf_token}".encode(),
        hashlib.sha256,
    ).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def create_session_token(
    *,
    user_id: uuid.UUID,
    hashed_password: str,
    status_changed_at: datetime,
    csrf_token: str,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    version = credential_version(hashed_password, status_changed_at)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
            "type": "session",
            "cv": version,
            "csrf": _csrf_digest(csrf_token, version),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_session_token(token: str | None) -> SessionClaims | None:
    if not token or len(token) > MAX_SESSION_TOKEN_LENGTH:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["sub", "iat", "exp", "type", "cv", "csrf"]},
        )
        if payload.get("type") != "session":
            return None
        user_id = uuid.UUID(payload["sub"])
        version = payload["cv"]
        csrf_digest = payload["csrf"]
        if not isinstance(version, str) or not version:
            return None
        if not isinstance(csrf_digest, str) or not csrf_digest:
            return None
        return SessionClaims(user_id, version, csrf_digest)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def session_matches_password(
    claims: SessionClaims,
    hashed_password: str,
    status_changed_at: datetime,
) -> bool:
    return hmac.compare_digest(
        claims.credential_version,
        credential_version(hashed_password, status_changed_at),
    )


def csrf_matches_session(claims: SessionClaims, csrf_token: str) -> bool:
    return hmac.compare_digest(
        claims.csrf_digest,
        _csrf_digest(csrf_token, claims.credential_version),
    )
