import uuid
import importlib.util
import inspect

from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.v2.dependencies import get_current_account, get_db
from app.core.client_ip import resolve_client_ip
from app.core.config import settings
from app.main import app
from app.models import RateLimitBucket
from app.services.rate_limit_service import (
    POLICIES,
    RateLimitAction,
    RateLimitDimension,
    RateLimitExceeded,
    RateLimitRule,
    RateLimitStorageError,
    digest_rate_limit_key,
    enforce_rate_limit,
    normalize_rate_limit_email,
)
from app.models.enums import AccountStatus, GlobalRole


NOW = datetime(2026, 8, 24, 12, 7, tzinfo=timezone.utc)


def _request(
    peer: str = "192.0.2.10", headers: list[tuple[bytes, bytes]] | None = None
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers or [],
            "client": (peer, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_rate_limit_bucket_metadata_is_frozen_and_minimal() -> None:
    table = RateLimitBucket.__table__
    assert set(table.columns.keys()) == {
        "action",
        "dimension",
        "key_digest",
        "window_start",
        "attempt_count",
        "expires_at",
    }
    assert table.primary_key.name == "pk_rate_limit_buckets"
    assert {constraint.name for constraint in table.constraints} >= {
        "ck_rate_limit_buckets_action_nonblank",
        "ck_rate_limit_buckets_dimension_nonblank",
        "ck_rate_limit_buckets_digest_length",
        "ck_rate_limit_buckets_attempt_count_positive",
        "ck_rate_limit_buckets_expiry_after_window",
    }
    assert {index.name for index in table.indexes} == {
        "ix_rate_limit_buckets_expires_at"
    }


def test_rate_limit_migration_is_additive_and_frozen() -> None:
    path = "alembic/versions/c3d172b18308_create_rate_limit_buckets.py"
    spec = importlib.util.spec_from_file_location("rate_limit_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    source = inspect.getsource(migration)
    assert migration.down_revision == "e4f5a6b7c8d9"
    assert 'op.create_table(\n        "rate_limit_buckets"' in source
    assert "app.models" not in source
    assert "op.drop_table(\"rate_limit_buckets\")" in source


def test_policies_match_the_approved_defaults() -> None:
    expected = {
        RateLimitAction.LOGIN: (("IP", 20, 900), ("EMAIL", 8, 900), ("IP_EMAIL", 5, 900)),
        RateLimitAction.REGISTRATION: (("IP", 5, 3600), ("EMAIL", 3, 86400)),
        RateLimitAction.VERIFICATION_RESEND: (("IP", 10, 3600), ("EMAIL", 3, 3600)),
        RateLimitAction.VERIFICATION_SUBMIT: (("IP", 20, 900),),
        RateLimitAction.PASSWORD_RECOVERY: (("IP", 10, 3600), ("EMAIL", 3, 3600)),
        RateLimitAction.PASSWORD_RESET: (("IP", 20, 900),),
        RateLimitAction.PASSWORD_CHANGE: (("USER_ACTOR", 5, 900),),
        RateLimitAction.ADMIN_APPROVE: (("ADMIN_ACTOR", 30, 60),),
        RateLimitAction.ADMIN_REJECT: (("ADMIN_ACTOR", 30, 60),),
    }
    assert {
        action: tuple(
            (rule.dimension.value, rule.maximum, rule.window_seconds)
            for rule in rules
        )
        for action, rules in POLICIES.items()
    } == expected


def test_email_and_digest_are_normalized_private_and_deterministic() -> None:
    assert normalize_rate_limit_email(" Person@Example.COM ") == "person@example.com"
    first = digest_rate_limit_key(
        action=RateLimitAction.LOGIN,
        dimension=RateLimitDimension.EMAIL,
        value="person@example.com",
    )
    second = digest_rate_limit_key(
        action=RateLimitAction.LOGIN,
        dimension=RateLimitDimension.EMAIL,
        value=normalize_rate_limit_email(" PERSON@example.com "),
    )
    assert first == second
    assert len(first) == 32
    assert b"person@example.com" not in first
    assert first != digest_rate_limit_key(
        action=RateLimitAction.REGISTRATION,
        dimension=RateLimitDimension.EMAIL,
        value="person@example.com",
    )
    assert first != digest_rate_limit_key(
        action=RateLimitAction.LOGIN,
        dimension=RateLimitDimension.EMAIL,
        value="another@example.com",
    )
    assert first != digest_rate_limit_key(
        action=RateLimitAction.LOGIN,
        dimension=RateLimitDimension.IP,
        value="person@example.com",
    )


def test_untrusted_forwarded_headers_are_ignored_and_ipv6_is_canonical() -> None:
    headers = [
        (b"x-forwarded-for", b"203.0.113.99"),
        (b"cf-connecting-ip", b"203.0.113.98"),
    ]
    with patch.object(settings, "RATE_LIMIT_TRUSTED_PROXY_CIDRS", []):
        assert resolve_client_ip(_request("2001:0db8:0:0::1", headers)) == "2001:db8::1"


def test_trusted_proxy_chain_and_malformed_chain_are_safe() -> None:
    with patch.object(settings, "RATE_LIMIT_TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"]):
        valid = _request(
            "10.0.0.2",
            [(b"x-forwarded-for", b"203.0.113.8, 10.0.0.1")],
        )
        malformed = _request(
            "10.0.0.2",
            [(b"x-forwarded-for", b"attacker, 10.0.0.1")],
        )
        assert resolve_client_ip(valid) == "203.0.113.8"
        assert resolve_client_ip(malformed) == "10.0.0.2"


class _Result:
    def __init__(self, value: int):
        self.value = value

    def scalar_one(self) -> int:
        return self.value


def _session_with_count(count: int) -> MagicMock:
    db = MagicMock()
    db.execute.side_effect = [MagicMock(), _Result(count)]
    return db


def test_exact_threshold_allowed_and_next_attempt_rejected_after_commit() -> None:
    rule = (RateLimitRule(RateLimitDimension.IP, 5, 900),)
    with patch.dict(POLICIES, {RateLimitAction.LOGIN: rule}):
        allowed_db = _session_with_count(5)
        enforce_rate_limit(
            action=RateLimitAction.LOGIN,
            request=_request(),
            now=NOW,
            session_factory=lambda: allowed_db,
        )
        allowed_db.commit.assert_called_once_with()

        rejected_db = _session_with_count(6)
        with pytest.raises(RateLimitExceeded) as captured:
            enforce_rate_limit(
                action=RateLimitAction.LOGIN,
                request=_request(),
                now=NOW,
                session_factory=lambda: rejected_db,
            )
        assert captured.value.retry_after == 480
        rejected_db.commit.assert_called_once_with()
        rejected_db.rollback.assert_not_called()


def test_storage_failure_is_fail_closed() -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("private database detail")
    with pytest.raises(RateLimitStorageError):
        enforce_rate_limit(
            action=RateLimitAction.VERIFICATION_SUBMIT,
            request=_request(),
            now=NOW,
            session_factory=lambda: db,
        )
    db.rollback.assert_called_once_with()
    db.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v2/auth/login", {"email": "person@example.com", "password": "Password!"}),
        ("/api/v2/auth/registration-requests", {"email": "person@example.com", "password": "Password!", "first_name": "Ada", "last_name": "Lovelace"}),
        ("/api/v2/auth/email-verifications", {"token": "A" * 43}),
        ("/api/v2/auth/email-verifications/resend", {"email": "person@example.com"}),
        ("/api/v2/auth/password-recovery-requests", {"email": "person@example.com"}),
        ("/api/v2/auth/password-resets", {"token": "R" * 43, "new_password": "NewPassword!"}),
    ],
)
def test_public_routes_return_safe_429_before_domain_work(
    path: str, payload: dict[str, str]
) -> None:
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: iter([db])
    protected_calls = (
        "authenticate_session",
        "create_registration_with_verification",
        "verify_email_token",
        "resend_email_verification",
        "request_password_recovery",
        "reset_password",
    )
    with ExitStack() as stack:
        limiter = stack.enter_context(
            patch(
                "app.api.v2.identity.enforce_rate_limit",
                side_effect=RateLimitExceeded(37),
            )
        )
        domain_calls = [
            stack.enter_context(patch(f"app.api.v2.identity.{name}"))
            for name in protected_calls
        ]
        verification_delivery = stack.enter_context(
            patch("app.api.v2.identity.email_delivery.send_verification_email")
        )
        recovery_delivery = stack.enter_context(
            patch("app.api.v2.identity.email_delivery.send_password_reset_email")
        )
        client = stack.enter_context(TestClient(app))
        response = client.post(path, json=payload)
    app.dependency_overrides.clear()
    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert "digest" not in response.text.lower()
    limiter.assert_called_once()
    for domain_call in domain_calls:
        domain_call.assert_not_called()
    verification_delivery.assert_not_called()
    recovery_delivery.assert_not_called()
    db.commit.assert_not_called()


def test_preflight_and_unauthorized_admin_requests_do_not_consume_limits() -> None:
    with patch("app.api.v2.identity.enforce_rate_limit") as limiter, TestClient(
        app
    ) as client:
        preflight = client.options(
            "/api/v2/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        unauthorized = client.post(
            f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve"
        )

    assert preflight.status_code == 200
    assert unauthorized.status_code == 401
    limiter.assert_not_called()


def test_admin_rate_limit_runs_after_authorization_and_before_mutation() -> None:
    admin = SimpleNamespace(
        id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN,
    )
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: iter([db])
    app.dependency_overrides[get_current_account] = lambda: admin
    with patch(
        "app.api.v2.identity.enforce_rate_limit",
        side_effect=RateLimitExceeded(12),
    ) as limiter, patch(
        "app.api.v2.identity.approve_registration_request"
    ) as mutation, TestClient(app) as client:
        response = client.post(
            f"/api/v2/admin/account-requests/{uuid.uuid4()}/approve"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 429
    assert limiter.call_args.kwargs["actor_id"] == admin.id
    mutation.assert_not_called()


def teardown_function() -> None:
    app.dependency_overrides.clear()
