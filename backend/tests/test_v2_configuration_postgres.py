import uuid

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v2.dependencies import get_current_account, get_db
from app.core.security import hash_password, verify_password
from app.core.session_security import create_session_token, decode_session_token, session_matches_password
from app.db import session as db_session
from app.main import app
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import (
    AccountStatus,
    CalendarVisibility,
    GlobalRole,
    WorkspaceKind,
)
from app.services.rate_limit_service import (
    RateLimitAction,
    RateLimitExceeded,
    enforce_rate_limit,
)
from tests.postgres_safety import (
    alembic_config_for_test_database,
    disposable_postgres_database,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _user(*, email: str, global_role: GlobalRole | None = None) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("CurrentPassword!"),
        first_name="Ada",
        last_name="Lovelace",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=global_role,
        email_verified_at=now,
        status_changed_at=now,
    )


def _client(session: Session, account: User, *, raise_server_exceptions: bool = True) -> TestClient:
    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_account] = lambda: account
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_profile_contract_round_trips_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source = make_url(db_session.DATABASE_URL).set(database="postgres")
    with disposable_postgres_database(
        source,
        database_name="lifemanager_test",
        explicit_test_intent=True,
    ) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        config = alembic_config_for_test_database(
            target_url,
            backend_root=BACKEND_ROOT,
            explicit_test_intent=True,
        )
        command.upgrade(config, "head")
        engine = sa.create_engine(target_url)
        try:
            columns = {column["name"] for column in sa.inspect(engine).get_columns("users")}
            assert {"first_name", "last_name", "timezone", "lock_version"} <= columns
            assert {"full_name", "username", "language"}.isdisjoint(columns)

            with Session(engine) as setup:
                first = _user(email="profile-a@example.com")
                second = _user(email="profile-b@example.com", global_role=GlobalRole.GLOBAL_ADMIN)
                setup.add_all([first, second]); setup.commit()
                first_id, second_id = first.id, second.id

            with Session(engine) as session:
                account = session.get(User, first_id)
                assert account is not None
                with _client(session, account) as client:
                    initial = client.get("/api/v2/configuration/profile")
                    assert initial.status_code == 200
                    assert initial.json()["first_name"] == "Ada"
                    assert initial.json()["lock_version"] == 1

                    payload = {"first_name": "  Augusta  ", "last_name": " King ", "timezone": "Europe/London", "lock_version": 1}
                    updated = client.patch("/api/v2/configuration/profile", json=payload)
                    assert updated.status_code == 200
                    assert updated.json()["first_name"] == "Augusta"
                    assert updated.json()["last_name"] == "King"
                    assert updated.json()["timezone"] == "Europe/London"
                    assert updated.json()["lock_version"] == 2

                    after = client.get("/api/v2/configuration/profile")
                    assert after.status_code == 200
                    assert (after.json()["first_name"], after.json()["timezone"], after.json()["lock_version"]) == ("Augusta", "Europe/London", 2)

                    stale = client.patch("/api/v2/configuration/profile", json={**payload, "lock_version": 1})
                    assert stale.status_code == 409

                    invalid_timezone = client.patch("/api/v2/configuration/profile", json={**payload, "timezone": "Not/A-Timezone", "lock_version": 2})
                    assert invalid_timezone.status_code == 422
                    hostile = client.patch("/api/v2/configuration/profile", json={**payload, "lock_version": 2, "email": "changed@example.com", "account_status": "DISABLED", "global_role": "GLOBAL_ADMIN"})
                    assert hostile.status_code == 422

                    old_session = decode_session_token(create_session_token(
                        user_id=account.id,
                        hashed_password=account.hashed_password,
                        status_changed_at=account.status_changed_at,
                        csrf_token="csrf-test-value",
                    ))
                    assert old_session is not None
                    with patch("app.api.v2.configuration.enforce_rate_limit"):
                        password_changed = client.post(
                            "/api/v2/configuration/password",
                            json={
                                "current_password": "CurrentPassword!",
                                "new_password": "NewPassword!",
                            },
                        )
                    assert password_changed.status_code == 204
                    session.refresh(account)
                    assert verify_password("NewPassword!", account.hashed_password)
                    assert not verify_password("CurrentPassword!", account.hashed_password)
                    assert not session_matches_password(old_session, account.hashed_password, account.status_changed_at)

                    request = Request({
                        "type": "http",
                        "method": "POST",
                        "path": "/api/v2/configuration/password",
                        "headers": [],
                        "client": ("127.0.0.1", 12345),
                        "server": ("testserver", 80),
                        "scheme": "http",
                        "query_string": b"",
                    })
                    for _ in range(5):
                        enforce_rate_limit(
                            action=RateLimitAction.PASSWORD_CHANGE,
                            request=request,
                            actor_id=account.id,
                            session_factory=lambda: Session(engine),
                        )
                    with pytest.raises(RateLimitExceeded):
                        enforce_rate_limit(
                            action=RateLimitAction.PASSWORD_CHANGE,
                            request=request,
                            actor_id=account.id,
                            session_factory=lambda: Session(engine),
                        )

            with Session(engine) as verify:
                persisted = verify.get(User, first_id)
                other = verify.get(User, second_id)
                assert persisted is not None and other is not None
                assert (persisted.first_name, persisted.last_name, persisted.timezone, persisted.lock_version) == ("Augusta", "King", "Europe/London", 2)
                assert persisted.email == "profile-a@example.com"
                assert verify_password("NewPassword!", persisted.hashed_password)
                assert persisted.account_status == AccountStatus.ACTIVE
                assert persisted.global_role is None
                assert (other.first_name, other.timezone, other.lock_version) == ("Ada", "America/Lima", 1)

            def fail_profile_update(_conn, _cursor, statement, _parameters, _context, _many):
                if statement.lstrip().upper().startswith("UPDATE USERS"):
                    raise RuntimeError("forced persistence failure")

            sa.event.listen(engine, "before_cursor_execute", fail_profile_update)
            try:
                with Session(engine) as session:
                    account = session.get(User, first_id)
                    assert account is not None
                    with _client(session, account, raise_server_exceptions=False) as client:
                        failed = client.patch("/api/v2/configuration/profile", json={"first_name": "Should Not Persist", "last_name": "King", "timezone": "UTC", "lock_version": 2})
                    assert failed.status_code == 500
            finally:
                sa.event.remove(engine, "before_cursor_execute", fail_profile_update)

            with Session(engine) as verify:
                persisted = verify.get(User, first_id)
                assert persisted is not None
                assert (persisted.first_name, persisted.timezone, persisted.lock_version) == ("Augusta", "Europe/London", 2)
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def test_calendar_privacy_round_trips_per_active_shared_membership_on_disposable_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_url(db_session.DATABASE_URL).set(database="postgres")
    with disposable_postgres_database(
        source,
        database_name="lifemanager_test",
        explicit_test_intent=True,
    ) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(
            alembic_config_for_test_database(
                target_url,
                backend_root=BACKEND_ROOT,
                explicit_test_intent=True,
            ),
            "head",
        )
        engine = sa.create_engine(target_url)
        try:
            with Session(engine) as setup:
                owner = _user(email="privacy-owner@example.com")
                member = _user(email="privacy-member@example.com")
                administrator = _user(
                    email="privacy-admin@example.com",
                    global_role=GlobalRole.GLOBAL_ADMIN,
                )
                setup.add_all([owner, member, administrator]); setup.flush()
                shared = Workspace(
                    name="Familia",
                    kind=WorkspaceKind.SHARED,
                    owner_user_id=owner.id,
                )
                personal = Workspace(
                    name="Personal",
                    kind=WorkspaceKind.PERSONAL,
                    owner_user_id=member.id,
                )
                setup.add_all([shared, personal]); setup.flush()
                setup.add_all([
                    WorkspaceMember(workspace_id=shared.id, user_id=owner.id),
                    WorkspaceMember(workspace_id=shared.id, user_id=member.id),
                    WorkspaceMember(workspace_id=personal.id, user_id=member.id),
                ])
                setup.commit()
                shared_id, personal_id = shared.id, personal.id
                member_id, administrator_id = member.id, administrator.id

            with Session(engine) as session:
                member = session.get(User, member_id)
                assert member is not None
                with _client(session, member) as client:
                    initial = client.get(f"/api/v2/workspaces/{shared_id}/calendar-visibility")
                    assert initial.status_code == 200
                    assert initial.json() == {"visibility": "HIDE", "lock_version": 1}

                    updated = client.patch(
                        f"/api/v2/workspaces/{shared_id}/calendar-visibility",
                        json={"visibility": "AVAILABILITY_ONLY", "lock_version": 1},
                    )
                    assert updated.status_code == 200
                    assert updated.json() == {
                        "visibility": "AVAILABILITY_ONLY",
                        "lock_version": 2,
                    }
                    stale = client.patch(
                        f"/api/v2/workspaces/{shared_id}/calendar-visibility",
                        json={"visibility": "SHOW_DETAILS", "lock_version": 1},
                    )
                    assert stale.status_code == 409
                    assert client.get(
                        f"/api/v2/workspaces/{personal_id}/calendar-visibility"
                    ).status_code == 404

            with Session(engine) as verify:
                persisted = verify.scalar(
                    sa.select(WorkspaceMember).where(
                        WorkspaceMember.workspace_id == shared_id,
                        WorkspaceMember.user_id == member_id,
                    )
                )
                assert persisted is not None
                assert persisted.calendar_visibility == CalendarVisibility.AVAILABILITY_ONLY
                assert persisted.lock_version == 2

                administrator = verify.get(User, administrator_id)
                assert administrator is not None
                with _client(verify, administrator) as client:
                    assert client.get(
                        f"/api/v2/workspaces/{shared_id}/calendar-visibility"
                    ).status_code == 404
        finally:
            app.dependency_overrides.clear()
            engine.dispose()
