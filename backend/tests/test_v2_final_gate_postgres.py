import os
import uuid

from datetime import datetime, timezone
from urllib.parse import urlparse
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_db
from app.core.config import settings
from app.core.security import hash_password
from app.main import app
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, WorkspaceKind


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("final identity gate refuses non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {
        "lifemanager_test",
        "lifemanager_v2_test",
    }:
        pytest.fail("final identity gate requires an allowlisted disposable database")
    return url


def test_complete_registration_approval_session_and_logout_lifecycle() -> None:
    engine = sa.create_engine(_local_test_url())
    db = Session(engine)
    admin_password = "AdminPassword!"
    user_password = "UserPassword!"
    now = datetime.now(timezone.utc)
    admin = User(
        id=uuid.uuid4(),
        email=f"gate-admin-{uuid.uuid4()}@example.com",
        hashed_password=hash_password(admin_password),
        first_name="Gate",
        last_name="Admin",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN,
        email_verified_at=now,
        status_changed_at=now,
    )
    db.add(admin)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("app.api.v2.identity._enforce_rate_limit"), patch(
            "app.api.v2.identity._verify_anti_bot"
        ), patch(
            "app.api.v2.identity.email_delivery.send_verification_email"
        ) as delivery, TestClient(app) as client:
            email = f"gate-user-{uuid.uuid4()}@example.com"
            registration = client.post(
                "/api/v2/auth/registration-requests",
                json={
                    "email": email,
                    "password": user_password,
                    "first_name": "Gate",
                    "last_name": "User",
                    "timezone": "America/Lima",
                },
            )
            assert registration.status_code == 202
            raw_verification_token = delivery.call_args.args[0].raw_token
            pending_email = db.scalar(sa.select(User).where(User.email == email))
            assert pending_email is not None
            assert pending_email.account_status == AccountStatus.PENDING_EMAIL_VERIFICATION

            verification = client.post(
                "/api/v2/auth/email-verifications",
                json={"token": raw_verification_token},
            )
            assert verification.status_code == 200
            db.refresh(pending_email)
            assert pending_email.account_status == AccountStatus.PENDING_APPROVAL

            admin_login = client.post(
                "/api/v2/auth/login",
                json={"email": admin.email, "password": admin_password},
            )
            assert admin_login.status_code == 200
            admin_csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
            approval = client.post(
                f"/api/v2/admin/account-requests/{pending_email.id}/approve",
                headers={
                    "Origin": "http://localhost:5173",
                    settings.CSRF_HEADER_NAME: admin_csrf,
                },
            )
            assert approval.status_code == 200
            db.refresh(pending_email)
            assert pending_email.account_status == AccountStatus.ACTIVE

            workspace = db.scalar(
                sa.select(Workspace).where(
                    Workspace.owner_user_id == pending_email.id,
                    Workspace.kind == WorkspaceKind.PERSONAL,
                )
            )
            assert workspace is not None
            assert db.scalar(
                sa.select(sa.func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace.id,
                    WorkspaceMember.user_id == pending_email.id,
                )
            ) == 1

            user_login = client.post(
                "/api/v2/auth/login",
                json={"email": email, "password": user_password},
            )
            assert user_login.status_code == 200
            assert "token" not in user_login.text.lower()
            assert client.get("/api/v2/me").status_code == 200

            user_csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
            logout = client.post(
                "/api/v2/auth/logout",
                headers={
                    "Origin": "http://localhost:5173",
                    settings.CSRF_HEADER_NAME: user_csrf,
                },
            )
            assert logout.status_code == 204
            assert client.get("/api/v2/me").status_code == 401
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
