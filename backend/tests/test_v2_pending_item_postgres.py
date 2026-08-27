import uuid

from concurrent.futures import ThreadPoolExecutor
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
from app.services.v2_pending_item import PendingItemConflictError, PendingItemReferenceUnavailableError, correct_pending_item, create_pending_item, delete_pending_item, list_pending_items, update_pending_progress
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
            member = db.get(User, member_id)
            member_membership = db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == member_id))
            member_access = WorkspaceAccess(workspace, member_membership)
            update_pending_progress(db, access=member_access, actor=member, pending_item_id=first.id, progress=None, comment="Comentario sin cambio", expected_version=first.lock_version, local_date=date(2026, 9, 8))
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
            assert [row.actor_user_id for row in histories] == [owner_id, member_id, owner_id, owner_id, owner_id, owner_id]
            assert all(row.recorded_at is not None for row in histories)

            samples = [
                PendingItem(workspace_id=workspace_id, category_id=category_id, responsible_user_id=member_id, created_by_user_id=owner_id, name="Activo atrasado", is_active=True, planned_date=date(2026, 9, 8), progress=40),
                PendingItem(workspace_id=workspace_id, category_id=category_id, responsible_user_id=member_id, created_by_user_id=owner_id, name="A tiempo", is_active=True, planned_date=date(2026, 9, 10), progress=100, completion_date=date(2026, 9, 10)),
                PendingItem(workspace_id=workspace_id, category_id=category_id, responsible_user_id=member_id, created_by_user_id=owner_id, name="Con adelanto", is_active=True, planned_date=date(2026, 9, 12), progress=100, completion_date=date(2026, 9, 10)),
                PendingItem(workspace_id=workspace_id, category_id=category_id, responsible_user_id=member_id, created_by_user_id=owner_id, name="Con retraso", is_active=True, planned_date=date(2026, 9, 8), progress=100, completion_date=date(2026, 9, 10)),
                PendingItem(workspace_id=workspace_id, category_id=category_id, responsible_user_id=member_id, created_by_user_id=owner_id, name="Inactivo", is_active=False, planned_date=None, progress=0),
            ]
            db.add_all(samples); db.commit()
            for compliance, expected_name in (("EN_PLAZO", "Compra"), ("ATRASADO", "Activo atrasado"), ("A_TIEMPO", "A tiempo"), ("CON_ADELANTO", "Con adelanto"), ("CON_RETRASO", "Con retraso")):
                rows, _ = list_pending_items(db, workspace_id=workspace_id, local_date=date(2026, 9, 10), page=1, page_size=25, compliance=compliance)
                assert expected_name in {row[0].name for row in rows}
            filtered, filtered_total = list_pending_items(db, workspace_id=workspace_id, local_date=date(2026, 9, 10), page=1, page_size=25, is_active=True, responsible_user_id=member_id, category_id=category_id, state="EN_PROCESO", planned_from=date(2026, 9, 1), planned_to=date(2026, 9, 9), search="ATRASADO")
            assert filtered_total == 1 and filtered[0][0].name == "Activo atrasado"
            inactive, _ = list_pending_items(db, workspace_id=workspace_id, local_date=date(2026, 9, 10), page=1, page_size=25, is_active=False)
            assert [row[0].name for row in inactive] == ["Inactivo"]

            first = db.get(PendingItem, first.id)
            delete_pending_item(db, access=access, pending_item_id=first.id, expected_version=first.lock_version)
            db.commit()
            assert db.get(PendingItem, first.id) is None
            assert db.scalar(sa.select(sa.func.count()).select_from(PendingItemHistory).where(PendingItemHistory.pending_item_id == first.id)) == 0
            assert db.get(PendingItem, untouched.id) is not None

            race = create_pending_item(db, access=access, actor=owner, item_in=PendingItemCreate(category_id=category_id, responsible_user_id=member_id, name="Carrera", planned_date=date(2026, 9, 20)))
            db.commit()
            race_id, race_version = race.id, race.lock_version

            def race_progress(value: int) -> str:
                with Session(engine) as concurrent_db:
                    concurrent_actor = concurrent_db.get(User, owner_id)
                    concurrent_workspace = concurrent_db.get(Workspace, workspace_id)
                    concurrent_membership = concurrent_db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == owner_id))
                    try:
                        update_pending_progress(concurrent_db, access=WorkspaceAccess(concurrent_workspace, concurrent_membership), actor=concurrent_actor, pending_item_id=race_id, progress=value, expected_version=race_version, local_date=date(2026, 9, 12))
                        concurrent_db.commit()
                        return "updated"
                    except PendingItemConflictError:
                        concurrent_db.rollback()
                        return "conflict"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(race_progress, (10, 20)))
            assert sorted(outcomes) == ["conflict", "updated"]
            db.expire_all()
            assert db.get(PendingItem, race_id).lock_version == race_version + 1
            assert db.scalar(sa.select(sa.func.count()).select_from(PendingItemHistory).where(PendingItemHistory.pending_item_id == race_id)) == 1

            pending_fks = {row["name"]: row for row in sa.inspect(engine).get_foreign_keys("pending_item_history")}
            assert pending_fks["fk_pending_item_history_item_workspace"]["options"]["ondelete"] == "CASCADE"
            assert pending_fks["fk_pending_item_history_actor_membership"]["options"]["ondelete"] == "RESTRICT"
        engine.dispose()
