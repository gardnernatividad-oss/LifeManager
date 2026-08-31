import uuid

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import Activity, ActivityMaster, Category, MasterTask, PendingItem, Project, ProjectStage, Task, User, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, MembershipStatus, WorkspaceKind
from app.services.v2_report import get_report_summary
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_report_summary_aggregates_workspace_data_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Reports PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            now = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
            owner = User(id=uuid.uuid4(), email="reports@example.test", hashed_password="hash", first_name="Ana", last_name="Uno", timezone="America/Lima", account_status=AccountStatus.ACTIVE, email_verified_at=now, status_changed_at=now)
            member = User(id=uuid.uuid4(), email="member@example.test", hashed_password="hash", first_name="Beto", last_name="Dos", timezone="America/Lima", account_status=AccountStatus.ACTIVE, email_verified_at=now, status_changed_at=now)
            outsider = User(id=uuid.uuid4(), email="outside@example.test", hashed_password="hash", first_name="Cata", last_name="Tres", timezone="America/Lima", account_status=AccountStatus.ACTIVE, email_verified_at=now, status_changed_at=now)
            workspace = Workspace(id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED, owner_user_id=owner.id)
            foreign = Workspace(id=uuid.uuid4(), name="Ajeno", kind=WorkspaceKind.PERSONAL, owner_user_id=outsider.id)
            db.add_all([owner, member, outsider, workspace, foreign]); db.flush()
            db.add_all([
                WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=workspace.id, user_id=member.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=foreign.id, user_id=outsider.id, status=MembershipStatus.ACTIVE),
            ]); db.flush()
            category_a = Category(id=uuid.uuid4(), workspace_id=workspace.id, name="Casa", normalized_name="casa")
            category_b = Category(id=uuid.uuid4(), workspace_id=workspace.id, name="Salud", normalized_name="salud")
            foreign_category = Category(id=uuid.uuid4(), workspace_id=foreign.id, name="Ajeno", normalized_name="ajeno")
            db.add_all([category_a, category_b, foreign_category]); db.flush()
            master_task = MasterTask(id=uuid.uuid4(), workspace_id=workspace.id, category_id=category_a.id, name="Comprar", normalized_name="comprar")
            activity_master = ActivityMaster(id=uuid.uuid4(), workspace_id=workspace.id, category_id=category_a.id, name="Consulta", normalized_name="consulta")
            db.add_all([master_task, activity_master]); db.flush()
            db.add_all([
                Task(id=uuid.uuid4(), workspace_id=workspace.id, master_task_id=master_task.id, responsible_user_id=owner.id, planned_date=date(2026, 8, 10), created_by_user_id=owner.id),
                Task(id=uuid.uuid4(), workspace_id=workspace.id, custom_name="Otra tarea real", custom_category_id=category_b.id, responsible_user_id=member.id, planned_date=date(2026, 8, 11), created_by_user_id=owner.id),
                PendingItem(id=uuid.uuid4(), workspace_id=workspace.id, category_id=category_a.id, responsible_user_id=owner.id, name="Pendiente", planned_date=date(2026, 8, 10), progress=20, created_by_user_id=owner.id),
            ]); db.flush()
            project = Project(id=uuid.uuid4(), workspace_id=workspace.id, category_id=category_a.id, leader_user_id=owner.id, name="Proyecto", created_by_user_id=owner.id)
            db.add(project); db.flush()
            db.add_all([
                ProjectStage(id=uuid.uuid4(), workspace_id=workspace.id, project_id=project.id, responsible_user_id=owner.id, name="Inicio", position=1, weight=50, planned_date=date(2026, 8, 9), progress=50),
                ProjectStage(id=uuid.uuid4(), workspace_id=workspace.id, project_id=project.id, responsible_user_id=member.id, name="Fin", position=2, weight=50, planned_date=date(2026, 8, 12), progress=0),
                Activity(id=uuid.uuid4(), workspace_id=workspace.id, organizer_user_id=owner.id, activity_master_id=activity_master.id, title="Consulta", starts_at=datetime(2026, 8, 10, 5, tzinfo=timezone.utc), ends_at=datetime(2026, 8, 10, 6, tzinfo=timezone.utc)),
                Activity(id=uuid.uuid4(), workspace_id=workspace.id, organizer_user_id=member.id, custom_category_id=category_b.id, title="Otra actividad real", starts_at=datetime(2026, 8, 12, 4, 30, tzinfo=timezone.utc), ends_at=datetime(2026, 8, 12, 5, 30, tzinfo=timezone.utc)),
                PendingItem(id=uuid.uuid4(), workspace_id=foreign.id, category_id=foreign_category.id, responsible_user_id=outsider.id, name="No visible", planned_date=date(2026, 8, 10), progress=0, created_by_user_id=outsider.id),
            ]); db.commit()

            all_counts = get_report_summary(db, workspace_id=workspace.id, timezone_name="America/Lima")
            assert (all_counts.tasks, all_counts.pending_items, all_counts.projects, all_counts.activities) == (2, 1, 1, 2)
            category_counts = get_report_summary(db, workspace_id=workspace.id, timezone_name="America/Lima", category_id=category_a.id)
            assert (category_counts.tasks, category_counts.pending_items, category_counts.projects, category_counts.activities) == (1, 1, 1, 1)
            owner_counts = get_report_summary(db, workspace_id=workspace.id, timezone_name="America/Lima", responsible_user_id=owner.id)
            assert (owner_counts.tasks, owner_counts.pending_items, owner_counts.projects, owner_counts.activities) == (1, 1, 1, 1)
            bounded = get_report_summary(db, workspace_id=workspace.id, timezone_name="America/Lima", date_from=date(2026, 8, 10), date_until=date(2026, 8, 11))
            assert (bounded.tasks, bounded.pending_items, bounded.projects, bounded.activities) == (2, 1, 0, 2)
        engine.dispose()
