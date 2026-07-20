from datetime import datetime, timedelta, timezone

import jwt as _jwt

from app.core.config import settings as _settings

__all__ = ["create_access_token", "decode_access_token"]


def create_access_token(
    *,
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    if not _settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")

    expiration = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return _jwt.encode(
        {
            "sub": subject,
            "exp": expiration,
            "type": "access",
        },
        _settings.SECRET_KEY,
        algorithm=_settings.ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    if not _settings.SECRET_KEY:
        return None

    try:
        payload = _jwt.decode(
            token,
            _settings.SECRET_KEY,
            algorithms=[_settings.ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
    except (_jwt.PyJWTError, TypeError, ValueError):
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    if payload.get("type") != "access":
        return None

    return subject
