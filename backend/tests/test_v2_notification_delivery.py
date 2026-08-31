import uuid

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import NotificationJob, User
from app.models.enums import NotificationJobStatus, NotificationType
from app.services.v2_notification_delivery import (
    NotificationContent,
    PushResult,
    claim_due_job_ids,
    compose_daily_review,
    compose_daily_summary,
)


def test_daily_summary_reuses_home_projection_and_supports_empty_day() -> None:
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    home = SimpleNamespace(today=(3, 1, 2, 2), attention=[object(), object()])
    with patch("app.services.v2_notification_delivery.get_home_summary", return_value=home) as get_home:
        content = compose_daily_summary(MagicMock(), user=user, now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc))
    assert content == NotificationContent("Resumen de hoy", "3 tareas · 1 pendiente · 2 etapas · 2 actividades · 2 atrasados", "HOME")
    assert get_home.call_args.kwargs["timezone_name"] == "America/Lima"
    with patch("app.services.v2_notification_delivery.get_home_summary", return_value=SimpleNamespace(today=(0, 0, 0, 0), attention=[])):
        assert "No tienes elementos" in compose_daily_summary(MagicMock(), user=user, now=datetime.now(timezone.utc)).body


def test_daily_review_reuses_review_selection_and_skips_empty() -> None:
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    selection = SimpleNamespace(tasks=[1, 2], pending_items=[1], project_stages=[1])
    with patch("app.services.v2_notification_delivery.get_global_review", return_value=selection) as get_review:
        content = compose_daily_review(MagicMock(), user=user, now=datetime(2026, 8, 31, 2, tzinfo=timezone.utc))
    assert content == NotificationContent("Revisión diaria", "2 tareas · 1 pendiente · 1 etapa por revisar", "REVIEW")
    assert get_review.call_args.kwargs["local_date"].isoformat() == "2026-08-30"
    empty = SimpleNamespace(tasks=[], pending_items=[], project_stages=[])
    with patch("app.services.v2_notification_delivery.get_global_review", return_value=empty):
        assert compose_daily_review(MagicMock(), user=user, now=datetime.now(timezone.utc)) is None


def test_claim_query_is_due_ordered_and_skip_locked() -> None:
    db = MagicMock(); db.scalars.return_value.all.return_value = []
    assert claim_due_job_ids(db, now=datetime(2026, 8, 30, tzinfo=timezone.utc), limit=25) == []
    sql = str(db.scalars.call_args.args[0])
    assert "notification_jobs.status IN" in sql
    assert "notification_jobs.scheduled_for <=" in sql
    assert "ORDER BY notification_jobs.scheduled_for, notification_jobs.id" in sql


def test_payload_contract_uses_only_safe_fields() -> None:
    content = NotificationContent("Resumen de hoy", "1 tarea", "HOME")
    payload = {"type": NotificationType.DAILY_SUMMARY_REMINDER.value, "title": content.title, "body": content.body, "destination": content.destination}
    assert set(payload) == {"type", "title", "body", "destination"}
    assert "url" not in payload and "workspace_id" not in payload and "email" not in payload
