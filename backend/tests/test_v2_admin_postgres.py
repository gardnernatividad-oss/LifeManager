import uuid
import threading

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import User, UserAccountStateEvent
from app.models.enums import AccountStatus, GlobalRole
from app.services.v2_admin import change_admin_account_state
from app.services.v2_identity import AccountStateConflictError
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_admin_state_transition_persists_event_and_rejects_stale_version(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Admin PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        db = Session(engine)
        now = datetime.now(timezone.utc)
        admin = User(id=uuid.uuid4(), email=f"admin-{uuid.uuid4()}@test.local", hashed_password="hash", first_name="Global", last_name="Admin", timezone="America/Lima", account_status=AccountStatus.ACTIVE, global_role=GlobalRole.GLOBAL_ADMIN, email_verified_at=now, status_changed_at=now)
        target = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@test.local", hashed_password="hash", first_name="Normal", last_name="User", timezone="America/Lima", account_status=AccountStatus.ACTIVE, email_verified_at=now, status_changed_at=now)
        db.add_all([admin, target]); db.commit()
        change_admin_account_state(db, user_id=target.id, expected_lock_version=1, new_status=AccountStatus.DISABLED, actor=admin, reason="TEST")
        db.commit()
        assert db.get(User, target.id).account_status == AccountStatus.DISABLED
        event = db.scalar(sa.select(UserAccountStateEvent).where(UserAccountStateEvent.user_id == target.id).order_by(UserAccountStateEvent.created_at.desc()))
        assert event is not None and event.actor_user_id == admin.id and event.to_status == AccountStatus.DISABLED
        with pytest.raises(AccountStateConflictError):
            change_admin_account_state(db, user_id=target.id, expected_lock_version=1, new_status=AccountStatus.ACTIVE, actor=admin, reason="STALE")
        db.rollback()
        db.expire_all()
        assert db.get(User, target.id).account_status == AccountStatus.DISABLED
        change_admin_account_state(db, user_id=target.id, expected_lock_version=2, new_status=AccountStatus.ACTIVE, actor=admin, reason="REACTIVATE")
        db.commit()
        target_id, admin_id = target.id, admin.id
        db.close()

        barrier = threading.Barrier(2)

        def disable_once() -> str:
            with Session(engine) as concurrent_db:
                actor = concurrent_db.get(User, admin_id)
                assert actor is not None
                barrier.wait(timeout=10)
                try:
                    change_admin_account_state(concurrent_db, user_id=target_id, expected_lock_version=3, new_status=AccountStatus.DISABLED, actor=actor, reason="CONCURRENT")
                    concurrent_db.commit()
                    return "disabled"
                except AccountStateConflictError:
                    concurrent_db.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(disable_once) for _ in range(2)]
            results = sorted(future.result() for future in futures)
        assert results == ["conflict", "disabled"]
        with Session(engine) as verify:
            persisted = verify.get(User, target_id)
            assert persisted is not None and persisted.account_status == AccountStatus.DISABLED and persisted.lock_version == 4
            assert verify.scalar(sa.select(sa.func.count()).select_from(UserAccountStateEvent).where(UserAccountStateEvent.user_id == target_id, UserAccountStateEvent.to_status == AccountStatus.DISABLED)) == 2
        engine.dispose()
