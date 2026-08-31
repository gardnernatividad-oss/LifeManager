import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import Notification, NotificationDelivery, NotificationJob, PushSubscription
from app.models.enums import NotificationJobStatus
from app.schemas.v2_notifications import PushSubscriptionCreate
from app.services.v2_notifications import PushSubscriptionConflictError, generate_scheduled_jobs, register_push_subscription
from app.services.v2_notification_delivery import NotificationContent, PushResult, deliver_job
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_notification_migration_dedupe_and_push_security_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}: pytest.skip("requires local disposable PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1"); monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        config = alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True)
        command.upgrade(config, "head")
        engine = sa.create_engine(target_url)
        inspector = sa.inspect(engine)
        assert "notification_jobs" in inspector.get_table_names()
        assert {item["name"] for item in inspector.get_unique_constraints("notification_jobs")} >= {"uq_notification_jobs_dedup_key"}
        assert "notification_id" in {item["name"] for item in inspector.get_columns("notification_jobs")}
        command.downgrade(config, "d1e2f3a4b5c6"); assert "notification_jobs" not in sa.inspect(engine).get_table_names()
        command.upgrade(config, "head")
        user_id, other_id = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at,timezone) VALUES (:id,:email,'hash','Notify','User','ACTIVE',now(),'America/Lima')"), [{"id": user_id, "email": "notify-pg@test.local"}, {"id": other_id, "email": "other-pg@test.local"}])

        start, end = datetime(2026, 8, 30, 11, 59, tzinfo=timezone.utc), datetime(2026, 8, 30, 12, 1, tzinfo=timezone.utc)
        def generate() -> int:
            with Session(engine) as session:
                created = generate_scheduled_jobs(session, window_start=start, window_end=end); session.commit(); return created
        with ThreadPoolExecutor(max_workers=2) as pool:
            counts = list(pool.map(lambda _: generate(), range(2)))
        with Session(engine) as db:
            assert sorted(counts) == [0, 2]
            assert db.scalar(sa.select(sa.func.count()).select_from(NotificationJob)) == 2
            payload = PushSubscriptionCreate.model_validate({"endpoint": "https://push.example/device", "keys": {"p256dh": "public-key", "auth": "auth-key"}})
            subscription = register_push_subscription(db, user_id=user_id, subscription_in=payload, user_agent="test"); db.commit()
            assert subscription.endpoint_ciphertext != str(payload.endpoint).encode()
            assert db.scalar(sa.select(sa.func.count()).select_from(PushSubscription)) == 1
            with pytest.raises(PushSubscriptionConflictError): register_push_subscription(db, user_id=other_id, subscription_in=payload, user_agent=None)
            db.rollback()

        class SequenceTransport:
            def __init__(self, results): self.results = iter(results); self.calls = []
            def send(self, **kwargs): self.calls.append(kwargs); return next(self.results)

        with Session(engine) as db:
            second_payload = PushSubscriptionCreate.model_validate({"endpoint": "https://push.example/device-2", "keys": {"p256dh": "public-key-2", "auth": "auth-key-2"}})
            register_push_subscription(db, user_id=user_id, subscription_in=second_payload, user_agent="test-2")
            job = db.scalar(sa.select(NotificationJob).where(NotificationJob.user_id == user_id))
            transport = SequenceTransport([PushResult.DELIVERED, PushResult.TRANSIENT_FAILURE])
            with patch("app.services.v2_notification_delivery.compose_daily_summary", return_value=NotificationContent("Resumen de hoy", "1 tarea", "HOME")):
                delivered = deliver_job(db, job_id=job.id, now=datetime(2026, 8, 30, 12, 1, tzinfo=timezone.utc), transport=transport)
            db.commit()
            assert delivered.status == NotificationJobStatus.FAILED
            assert db.scalar(sa.select(sa.func.count()).select_from(Notification)) == 1
            assert db.scalar(sa.select(sa.func.count()).select_from(NotificationDelivery)) == 2
            retry = SequenceTransport([PushResult.DELIVERED])
            with patch("app.services.v2_notification_delivery.compose_daily_summary", return_value=NotificationContent("Resumen de hoy", "1 tarea", "HOME")):
                delivered = deliver_job(db, job_id=job.id, now=datetime(2026, 8, 30, 12, 2, tzinfo=timezone.utc), transport=retry)
            db.commit()
            assert delivered.status == NotificationJobStatus.SENT
            assert len(retry.calls) == 1

        concurrent_payload = PushSubscriptionCreate.model_validate({"endpoint": "https://push.example/concurrent", "keys": {"p256dh": "concurrent-key", "auth": "concurrent-auth"}})
        with Session(engine) as db:
            register_push_subscription(db, user_id=other_id, subscription_in=concurrent_payload, user_agent="concurrent")
            concurrent_job_id = db.scalar(sa.select(NotificationJob.id).where(NotificationJob.user_id == other_id))
            db.commit()
        concurrent_transport = SequenceTransport([PushResult.DELIVERED])
        def deliver_concurrently():
            with Session(engine) as session:
                result = deliver_job(session, job_id=concurrent_job_id, now=datetime(2026, 8, 30, 12, 3, tzinfo=timezone.utc), transport=concurrent_transport)
                session.commit()
                return result.status if result else None
        with patch("app.services.v2_notification_delivery.compose_daily_summary", return_value=NotificationContent("Resumen de hoy", "Sin pendientes", "HOME")):
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(lambda _: deliver_concurrently(), range(2)))
        assert statuses.count(NotificationJobStatus.SENT) == 1
        assert statuses.count(None) == 1
        assert len(concurrent_transport.calls) == 1
        engine.dispose()
