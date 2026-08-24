import hashlib
import hmac
import math
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Callable

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.client_ip import resolve_client_ip
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import RateLimitBucket


class RateLimitAction(StrEnum):
    LOGIN = "LOGIN"
    REGISTRATION = "REGISTRATION"
    VERIFICATION_RESEND = "VERIFICATION_RESEND"
    VERIFICATION_SUBMIT = "VERIFICATION_SUBMIT"
    PASSWORD_RECOVERY = "PASSWORD_RECOVERY"
    PASSWORD_RESET = "PASSWORD_RESET"
    ADMIN_APPROVE = "ADMIN_APPROVE"
    ADMIN_REJECT = "ADMIN_REJECT"


class RateLimitDimension(StrEnum):
    IP = "IP"
    EMAIL = "EMAIL"
    IP_EMAIL = "IP_EMAIL"
    ADMIN_ACTOR = "ADMIN_ACTOR"


@dataclass(frozen=True)
class RateLimitRule:
    dimension: RateLimitDimension
    maximum: int
    window_seconds: int


POLICIES: dict[RateLimitAction, tuple[RateLimitRule, ...]] = {
    RateLimitAction.LOGIN: (
        RateLimitRule(RateLimitDimension.IP, 20, 15 * 60),
        RateLimitRule(RateLimitDimension.EMAIL, 8, 15 * 60),
        RateLimitRule(RateLimitDimension.IP_EMAIL, 5, 15 * 60),
    ),
    RateLimitAction.REGISTRATION: (
        RateLimitRule(RateLimitDimension.IP, 5, 60 * 60),
        RateLimitRule(RateLimitDimension.EMAIL, 3, 24 * 60 * 60),
    ),
    RateLimitAction.VERIFICATION_RESEND: (
        RateLimitRule(RateLimitDimension.IP, 10, 60 * 60),
        RateLimitRule(RateLimitDimension.EMAIL, 3, 60 * 60),
    ),
    RateLimitAction.VERIFICATION_SUBMIT: (
        RateLimitRule(RateLimitDimension.IP, 20, 15 * 60),
    ),
    RateLimitAction.PASSWORD_RECOVERY: (
        RateLimitRule(RateLimitDimension.IP, 10, 60 * 60),
        RateLimitRule(RateLimitDimension.EMAIL, 3, 60 * 60),
    ),
    RateLimitAction.PASSWORD_RESET: (
        RateLimitRule(RateLimitDimension.IP, 20, 15 * 60),
    ),
    RateLimitAction.ADMIN_APPROVE: (
        RateLimitRule(RateLimitDimension.ADMIN_ACTOR, 30, 60),
    ),
    RateLimitAction.ADMIN_REJECT: (
        RateLimitRule(RateLimitDimension.ADMIN_ACTOR, 30, 60),
    ),
}


@dataclass(eq=False)
class RateLimitExceeded(Exception):
    retry_after: int


class RateLimitStorageError(Exception):
    pass


def normalize_rate_limit_email(value: str) -> str:
    return str(value).strip().casefold()


def _hmac_key() -> bytes:
    if settings.RATE_LIMIT_HMAC_KEY:
        return settings.RATE_LIMIT_HMAC_KEY.encode()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        b"lifemanager:v2:rate-limit-key",
        hashlib.sha256,
    ).digest()


def digest_rate_limit_key(
    *, action: RateLimitAction, dimension: RateLimitDimension, value: str
) -> bytes:
    material = f"{action.value}\0{dimension.value}\0{value}".encode()
    return hmac.new(_hmac_key(), material, hashlib.sha256).digest()


def _window(now: datetime, seconds: int) -> tuple[datetime, datetime]:
    normalized = now.astimezone(timezone.utc)
    start_epoch = int(normalized.timestamp()) // seconds * seconds
    start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    return start, start + timedelta(seconds=seconds)


def _dimension_value(
    dimension: RateLimitDimension,
    *,
    client_ip: str,
    email: str | None,
    actor_id: uuid.UUID | None,
) -> str:
    if dimension == RateLimitDimension.IP:
        return client_ip
    if dimension == RateLimitDimension.EMAIL:
        if email is None:
            raise ValueError("email is required for this rate-limit policy")
        return normalize_rate_limit_email(email)
    if dimension == RateLimitDimension.IP_EMAIL:
        if email is None:
            raise ValueError("email is required for this rate-limit policy")
        return f"{client_ip}\0{normalize_rate_limit_email(email)}"
    if actor_id is None:
        raise ValueError("actor_id is required for this rate-limit policy")
    return str(actor_id)


def enforce_rate_limit(
    *,
    action: RateLimitAction,
    request: Request,
    email: str | None = None,
    actor_id: uuid.UUID | None = None,
    now: datetime | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> None:
    """Persist every attempt independently; requests 1..N pass and N+1 fails."""
    checked_at = now or datetime.now(timezone.utc)
    client_ip = resolve_client_ip(request)
    factory = session_factory or SessionLocal
    retry_after = 0
    db = factory()
    try:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at <= checked_at))
        for rule in POLICIES[action]:
            start, end = _window(checked_at, rule.window_seconds)
            value = _dimension_value(
                rule.dimension,
                client_ip=client_ip,
                email=email,
                actor_id=actor_id,
            )
            statement = (
                insert(RateLimitBucket)
                .values(
                    action=action.value,
                    dimension=rule.dimension.value,
                    key_digest=digest_rate_limit_key(
                        action=action,
                        dimension=rule.dimension,
                        value=value,
                    ),
                    window_start=start,
                    attempt_count=1,
                    expires_at=end,
                )
                .on_conflict_do_update(
                    constraint="pk_rate_limit_buckets",
                    set_={
                        "attempt_count": RateLimitBucket.attempt_count + 1,
                        "expires_at": end,
                    },
                )
                .returning(RateLimitBucket.attempt_count)
            )
            attempt_count = db.execute(statement).scalar_one()
            if attempt_count > rule.maximum:
                retry_after = max(
                    retry_after,
                    max(1, math.ceil((end - checked_at).total_seconds())),
                )
        db.commit()
    except Exception as error:
        db.rollback()
        raise RateLimitStorageError from error
    finally:
        db.close()

    if retry_after:
        raise RateLimitExceeded(retry_after=retry_after)
