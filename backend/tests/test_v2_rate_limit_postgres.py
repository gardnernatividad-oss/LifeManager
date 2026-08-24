import os
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi import Request
from sqlalchemy.orm import Session

from app.models import RateLimitBucket
from app.services.rate_limit_service import (
    POLICIES,
    RateLimitAction,
    RateLimitDimension,
    RateLimitExceeded,
    RateLimitRule,
    enforce_rate_limit,
)


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("rate-limit tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.fail("rate-limit tests require an allowlisted disposable database")
    return url


def _request(peer: str = "192.0.2.44") -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/", "headers": [],
        "client": (peer, 1234), "server": ("test", 80),
        "scheme": "http", "query_string": b"",
    })


def test_atomic_concurrent_limit_and_private_persistence() -> None:
    engine = sa.create_engine(_local_test_url(), pool_size=10)
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    action = RateLimitAction.VERIFICATION_SUBMIT
    with engine.begin() as connection:
        connection.execute(sa.delete(RateLimitBucket))

    def attempt(_: int) -> bool:
        try:
            enforce_rate_limit(
                action=action,
                request=_request(),
                now=now,
                session_factory=lambda: Session(engine),
            )
            return True
        except RateLimitExceeded:
            return False

    with patch.dict(
        POLICIES,
        {action: (RateLimitRule(RateLimitDimension.IP, 5, 900),)},
    ):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(attempt, range(6)))

    assert results.count(True) == 5
    assert results.count(False) == 1
    with engine.begin() as connection:
        row = connection.execute(
            sa.select(RateLimitBucket).where(RateLimitBucket.action == action.value)
        ).one()
        assert row.attempt_count == 6
        assert len(row.key_digest) == 32
        serialized = repr(row)
        assert "192.0.2.44" not in serialized

    with patch.dict(
        POLICIES,
        {action: (RateLimitRule(RateLimitDimension.IP, 5, 900),)},
    ):
        enforce_rate_limit(
            action=action,
            request=_request(),
            now=now + timedelta(seconds=901),
            session_factory=lambda: Session(engine),
        )

    with engine.begin() as connection:
        rows = connection.execute(
            sa.select(RateLimitBucket).where(RateLimitBucket.action == action.value)
        ).all()
        assert len(rows) == 1
        assert rows[0].attempt_count == 1
        connection.execute(sa.delete(RateLimitBucket))
    engine.dispose()


def test_login_ip_and_email_limits_block_spraying_and_distributed_attempts() -> None:
    engine = sa.create_engine(_local_test_url())
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    rules = (
        RateLimitRule(RateLimitDimension.IP, 2, 900),
        RateLimitRule(RateLimitDimension.EMAIL, 2, 900),
        RateLimitRule(RateLimitDimension.IP_EMAIL, 5, 900),
    )

    with engine.begin() as connection:
        connection.execute(sa.delete(RateLimitBucket))

    with patch.dict(POLICIES, {RateLimitAction.LOGIN: rules}):
        for email in ("one@example.com", "two@example.com"):
            enforce_rate_limit(
                action=RateLimitAction.LOGIN,
                request=_request("192.0.2.10"),
                email=email,
                now=now,
                session_factory=lambda: Session(engine),
            )
        with pytest.raises(RateLimitExceeded):
            enforce_rate_limit(
                action=RateLimitAction.LOGIN,
                request=_request("192.0.2.10"),
                email="three@example.com",
                now=now,
                session_factory=lambda: Session(engine),
            )

    with engine.begin() as connection:
        connection.execute(sa.delete(RateLimitBucket))

    with patch.dict(POLICIES, {RateLimitAction.LOGIN: rules}):
        for peer in ("192.0.2.20", "192.0.2.21"):
            enforce_rate_limit(
                action=RateLimitAction.LOGIN,
                request=_request(peer),
                email="same@example.com",
                now=now,
                session_factory=lambda: Session(engine),
            )
        with pytest.raises(RateLimitExceeded):
            enforce_rate_limit(
                action=RateLimitAction.LOGIN,
                request=_request("192.0.2.22"),
                email="same@example.com",
                now=now,
                session_factory=lambda: Session(engine),
            )

    with engine.begin() as connection:
        connection.execute(sa.delete(RateLimitBucket))
    engine.dispose()
