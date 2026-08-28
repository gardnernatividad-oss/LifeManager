import uuid

from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.services.v2_review import get_global_review
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_global_review_selection_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Review PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            user_id, other_id, admin_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            active_workspace, second_workspace, inactive_workspace, left_workspace, removed_workspace = (
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            )
            db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at,global_role) VALUES (:id,:email,'hash','Test','User','ACTIVE',now(),:role)"), [{"id": user_id, "email": "review@test.local", "role": None}, {"id": other_id, "email": "other@test.local", "role": None}, {"id": admin_id, "email": "admin@test.local", "role": "GLOBAL_ADMIN"}])
            for workspace_id, name, kind, lifecycle in ((active_workspace, "Personal", "PERSONAL", "ACTIVE"), (second_workspace, "Familia", "SHARED", "ACTIVE"), (inactive_workspace, "Archivado", "SHARED", "INACTIVE")):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id,lifecycle,deactivated_at) VALUES (:id,:name,:kind,:owner,:lifecycle,:deactivated_at)"), {"id": workspace_id, "name": name, "kind": kind, "owner": user_id, "lifecycle": lifecycle, "deactivated_at": date(2026, 8, 1) if lifecycle == "INACTIVE" else None})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": user_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": second_workspace, "user": other_id})
            db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id,lifecycle) VALUES (:id,'Anterior','SHARED',:owner,'ACTIVE')"), {"id": left_workspace, "owner": other_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": left_workspace, "user": other_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status,ended_at) VALUES (:id,:workspace,:user,'LEFT',now())"), {"id": uuid.uuid4(), "workspace": left_workspace, "user": user_id})
            db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id,lifecycle) VALUES (:id,'Retirado','SHARED',:owner,'ACTIVE')"), {"id": removed_workspace, "owner": other_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": removed_workspace, "user": other_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status,ended_at) VALUES (:id,:workspace,:user,'REMOVED',now())"), {"id": uuid.uuid4(), "workspace": removed_workspace, "user": user_id})
            category_ids, master_ids = {}, {}
            for workspace_id in (active_workspace, second_workspace, inactive_workspace, left_workspace, removed_workspace):
                category_ids[workspace_id], master_ids[workspace_id] = uuid.uuid4(), uuid.uuid4()
                db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,:name,:normalized)"), {"id": category_ids[workspace_id], "workspace": workspace_id, "name": f"Cat {workspace_id}", "normalized": str(workspace_id)})
                db.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,:name,:normalized)"), {"id": master_ids[workspace_id], "workspace": workspace_id, "category": category_ids[workspace_id], "name": f"Task {workspace_id}", "normalized": str(workspace_id)})
            task_ids = [uuid.uuid4() for _ in range(8)]
            db.execute(sa.text("INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id,result,resolved_at,resolved_by_user_id) VALUES (:id,:workspace,:master,:responsible,:planned,:creator,:result,:resolved,:resolver)"), [
                {"id": task_ids[0], "workspace": active_workspace, "master": master_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 28), "creator": user_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[1], "workspace": second_workspace, "master": master_ids[second_workspace], "responsible": user_id, "planned": date(2026, 8, 27), "creator": user_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[2], "workspace": second_workspace, "master": master_ids[second_workspace], "responsible": other_id, "planned": date(2026, 8, 27), "creator": user_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[3], "workspace": inactive_workspace, "master": master_ids[inactive_workspace], "responsible": user_id, "planned": date(2026, 8, 27), "creator": user_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[4], "workspace": left_workspace, "master": master_ids[left_workspace], "responsible": user_id, "planned": date(2026, 8, 27), "creator": other_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[5], "workspace": active_workspace, "master": master_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 29), "creator": user_id, "result": None, "resolved": None, "resolver": None},
                {"id": task_ids[6], "workspace": active_workspace, "master": master_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 26), "creator": user_id, "result": "COMPLETED", "resolved": date(2026, 8, 26), "resolver": user_id},
                {"id": task_ids[7], "workspace": removed_workspace, "master": master_ids[removed_workspace], "responsible": user_id, "planned": date(2026, 8, 27), "creator": other_id, "result": None, "resolved": None, "resolver": None},
            ])
            pending_id = uuid.uuid4()
            db.execute(sa.text("INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:responsible,'Pendiente',:planned,25,:creator)"), {"id": pending_id, "workspace": active_workspace, "category": category_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 28), "creator": user_id})
            project_id, stage_id = uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO projects (id,workspace_id,category_id,leader_user_id,name,created_by_user_id) VALUES (:id,:workspace,:category,:leader,'Proyecto',:creator)"), {"id": project_id, "workspace": second_workspace, "category": category_ids[second_workspace], "leader": user_id, "creator": user_id})
            db.execute(sa.text("INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date,progress) VALUES (:id,:workspace,:project,:responsible,'Etapa',0,100,:planned,50)"), {"id": stage_id, "workspace": second_workspace, "project": project_id, "responsible": user_id, "planned": date(2026, 8, 26)})
            db.commit()
            result = get_global_review(db, user_id=user_id, local_date=date(2026, 8, 28))
            assert [row[0].id for row in result.tasks] == [task_ids[1], task_ids[0]]
            assert [row[0].id for row in result.pending_items] == [pending_id]
            assert [row[0].id for row in result.project_stages] == [stage_id]
            assert not db.new and not db.dirty and not db.deleted
            assert get_global_review(db, user_id=admin_id, local_date=date(2026, 8, 28)) == type(result)(tasks=[], pending_items=[], project_stages=[])
        engine.dispose()
