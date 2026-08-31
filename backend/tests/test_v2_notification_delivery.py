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
    compose_activity_reminder,
    compose_pending_weekly,
    compose_project_weekly,
    pending_weekly_counts,
    project_weekly_counts,
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


def test_pending_weekly_uses_one_scoped_aggregate_and_compact_content() -> None:
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    db = MagicMock(); db.execute.return_value.one.return_value = (5, 2)
    assert pending_weekly_counts(db, user=user, now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc)) == (5, 2)
    sql = str(db.execute.call_args.args[0])
    assert "pending_items.responsible_user_id" in sql
    assert "pending_items.is_active IS true" in sql and "pending_items.progress <" in sql
    assert "workspace_members.status" in sql and "workspaces.lifecycle" in sql
    with patch("app.services.v2_notification_delivery.pending_weekly_counts", return_value=(5, 2)):
        content = compose_pending_weekly(db, user=user, now=datetime.now(timezone.utc))
    assert content == NotificationContent("Pendientes", "5 pendientes activos · 2 atrasados", "PENDING")
    with patch("app.services.v2_notification_delivery.pending_weekly_counts", return_value=(0, 0)):
        assert compose_pending_weekly(db, user=user, now=datetime.now(timezone.utc)) is None


def test_project_weekly_uses_leader_and_stage_aggregate() -> None:
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    db = MagicMock(); db.execute.return_value.one.return_value = (3, 1)
    assert project_weekly_counts(db, user=user, now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc)) == (3, 1)
    sql = str(db.execute.call_args.args[0])
    assert "projects.leader_user_id" in sql and "projects.is_active IS true" in sql
    assert "project_stages" in sql and "workspace_members.status" in sql
    with patch("app.services.v2_notification_delivery.project_weekly_counts", return_value=(3, 1)):
        content = compose_project_weekly(db, user=user, now=datetime.now(timezone.utc))
    assert content == NotificationContent("Proyectos", "3 proyectos activos · 1 atrasado", "PROJECTS")
    with patch("app.services.v2_notification_delivery.project_weekly_counts", return_value=(0, 0)):
        assert compose_project_weekly(db, user=user, now=datetime.now(timezone.utc)) is None


def test_activity_reminder_uses_current_occurrence_and_rejects_stale_schedule() -> None:
    user = User(id=uuid.uuid4(), timezone="America/Lima")
    activity_id = uuid.uuid4(); reminder_id = uuid.uuid4()
    starts_at = datetime(2026, 8, 30, 23, tzinfo=timezone.utc)
    activity = SimpleNamespace(id=activity_id, title="Cena familiar", starts_at=starts_at)
    reminder = SimpleNamespace(id=reminder_id, minutes_before=30)
    job = NotificationJob(
        id=uuid.uuid4(), user_id=user.id, notification_type=NotificationType.ACTIVITY_REMINDER,
        scheduled_for=datetime(2026, 8, 30, 22, 30, tzinfo=timezone.utc),
        dedup_key="activity", entity_type="ACTIVITY", entity_id=activity_id,
        status=NotificationJobStatus.PENDING,
    )
    db = MagicMock(); db.execute.return_value.one_or_none.return_value = (reminder, activity)
    content = compose_activity_reminder(db, job=job, user=user, now=datetime(2026, 8, 30, 22, 30, tzinfo=timezone.utc))
    assert content == NotificationContent("Cena familiar", "Comienza a las 18:00", "ACTIVITY")
    job.scheduled_for = datetime(2026, 8, 30, 22, tzinfo=timezone.utc)
    assert compose_activity_reminder(db, job=job, user=user, now=datetime(2026, 8, 30, 22, tzinfo=timezone.utc)) is None
