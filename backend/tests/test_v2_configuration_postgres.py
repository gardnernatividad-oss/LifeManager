import uuid

from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_account, get_db
from app.db import session as db_session
from app.main import app
from app.models import User
from app.models.enums import AccountStatus, GlobalRole
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
        hashed_password="fixture-hash",
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

            with Session(engine) as verify:
                persisted = verify.get(User, first_id)
                other = verify.get(User, second_id)
                assert persisted is not None and other is not None
                assert (persisted.first_name, persisted.last_name, persisted.timezone, persisted.lock_version) == ("Augusta", "King", "Europe/London", 2)
                assert persisted.email == "profile-a@example.com"
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
