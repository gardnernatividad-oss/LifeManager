import uuid

from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import PendingItem, PendingItemHistory, User, Workspace, WorkspaceMember
from app.schemas.v2_pending_item import PendingItemCreate
from app.services.v2_pending_item import PendingItemReferenceUnavailableError, correct_pending_item, create_pending_item, delete_pending_item, update_pending_progress
from app.services.v2_workspace import WorkspaceAccess
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_pending_lifecycle_history_and_cascade_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Pending PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        config = alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True)
        command.upgrade(config, "head")
        command.downgrade(config, "d5e6f7a8b9c0")
        command.upgrade(config, "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            owner_id, member_id, foreign_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            workspace_id, foreign_workspace_id = uuid.uuid4(), uuid.uuid4()
            for user_id, email in ((owner_id, "owner@test.local"), (member_id, "member@test.local"), (foreign_id, "foreign@test.local")):
                db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at) VALUES (:id,:email,'hash','Test','User','ACTIVE',now())"), {"id": user_id, "email": email})
            for current, owner, name in ((workspace_id, owner_id, "Shared"), (foreign_workspace_id, foreign_id, "Foreign")):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,'SHARED',:owner)"), {"id": current, "name": name, "owner": owner})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": current, "user": owner})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": member_id})
            category_id, foreign_category_id = uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Casa','casa')"), {"id": category_id, "workspace": workspace_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Otra','otra')"), {"id": foreign_category_id, "workspace": foreign_workspace_id})
            db.commit()
            owner = db.get(User, owner_id)
            workspace = db.get(Workspace, workspace_id)
            membership = db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == owner_id))
            access = WorkspaceAccess(workspace, membership)

            first = create_pending_item(db, access=access, actor=owner, item_in=PendingItemCreate(category_id=category_id, responsible_user_id=member_id, name="Compra", planned_date=date(2026, 9, 10)))
            untouched = create_pending_item(db, access=access, actor=owner, item_in=PendingItemCreate(category_id=category_id, responsible_user_id=member_id, name="Otro", planned_date=date(2026, 9, 15)))
            db.commit()
            with pytest.raises(PendingItemReferenceUnavailableError):
                create_pending_item(db, access=access, actor=owner, item_in=PendingItemCreate(category_id=foreign_category_id, responsible_user_id=member_id, name="Ajeno", planned_date=date(2026, 9, 10)))
            db.rollback()

            first = db.get(PendingItem, first.id)
            update_pending_progress(db, access=access, actor=owner, pending_item_id=first.id, progress=50, comment="Primer avance", expected_version=first.lock_version, local_date=date(2026, 9, 8))
            db.commit()
            first = db.get(PendingItem, first.id)
            update_pending_progress(db, access=access, actor=owner, pending_item_id=first.id, progress=None, comment="Comentario sin cambio", expected_version=first.lock_version, local_date=date(2026, 9, 8))
            db.commit()
            first = db.get(PendingItem, first.id)
            update_pending_progress(db, access=access, actor=owner, pending_item_id=first.id, progress=100, expected_version=first.lock_version, local_date=date(2026, 9, 9))
            db.commit()
            assert first.is_active is True and first.completion_date == date(2026, 9, 9)
            first = db.get(PendingItem, first.id)
            correct_pending_item(db, access=access, actor=owner, pending_item_id=first.id, progress=0, comment="Corrección", expected_version=first.lock_version)
            db.commit()
            assert first.completion_date is None and first.progress == 0
            first = db.get(PendingItem, first.id)
            update_pending_progress(db, access=access, actor=owner, pending_item_id=first.id, progress=100, expected_version=first.lock_version, local_date=date(2026, 9, 11))
            db.commit()
            assert first.completion_date == date(2026, 9, 11)
            first = db.get(PendingItem, first.id)
            correct_pending_item(db, access=access, actor=owner, pending_item_id=first.id, progress=0, expected_version=first.lock_version)
            db.commit()
            histories = db.scalars(sa.select(PendingItemHistory).where(PendingItemHistory.pending_item_id == first.id).order_by(PendingItemHistory.recorded_at, PendingItemHistory.id)).all()
            assert [row.event_type for row in histories] == ["TRACKING", "TRACKING", "TRACKING", "CORRECTION", "TRACKING", "CORRECTION"]
            assert [row.progress for row in histories] == [50, 50, 100, 0, 100, 0]
            assert histories[0].comment == "Primer avance" and histories[1].comment == "Comentario sin cambio"
            assert all(row.actor_user_id == owner_id and row.recorded_at is not None for row in histories)

            first = db.get(PendingItem, first.id)
            delete_pending_item(db, access=access, pending_item_id=first.id, expected_version=first.lock_version)
            db.commit()
            assert db.get(PendingItem, first.id) is None
            assert db.scalar(sa.select(sa.func.count()).select_from(PendingItemHistory).where(PendingItemHistory.pending_item_id == first.id)) == 0
            assert db.get(PendingItem, untouched.id) is not None
        engine.dispose()
