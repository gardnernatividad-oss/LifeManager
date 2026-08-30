import uuid

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.services.v2_home import get_home_summary
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_home_aggregates_v2_domains_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Home PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            user_id, workspace_id, category_id, master_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at) VALUES (:id,'home@test.local','hash','Home','User','ACTIVE',now())"), {"id": user_id})
            db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id,lifecycle) VALUES (:id,'Personal','PERSONAL',:owner,'ACTIVE')"), {"id": workspace_id, "owner": user_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": user_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Casa','casa')"), {"id": category_id, "workspace": workspace_id})
            db.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Comprar','comprar')"), {"id": master_id, "workspace": workspace_id, "category": category_id})
            db.execute(sa.text("INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id) VALUES (:id,:workspace,:master,:user,:planned,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "master": master_id, "user": user_id, "planned": date(2026, 8, 30)})
            db.execute(sa.text("INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:user,'Pago',:planned,20,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "category": category_id, "user": user_id, "planned": date(2026, 8, 29)})
            project_id = uuid.uuid4()
            db.execute(sa.text("INSERT INTO projects (id,workspace_id,category_id,leader_user_id,name,created_by_user_id) VALUES (:id,:workspace,:category,:user,'Mudanza',:user)"), {"id": project_id, "workspace": workspace_id, "category": category_id, "user": user_id})
            db.execute(sa.text("INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date,progress) VALUES (:id,:workspace,:project,:user,'Empacar',1,100,:planned,50)"), {"id": uuid.uuid4(), "workspace": workspace_id, "project": project_id, "user": user_id, "planned": date(2026, 8, 31)})
            db.commit()
            result = get_home_summary(db, user_id=user_id, timezone_name="America/Lima", now=datetime(2026, 8, 30, 17, tzinfo=timezone.utc))
            assert result.today == (1, 0, 0, 0)
            assert [(item.type, item.name) for item in result.attention] == [("PENDING_ITEM", "Pago")]
            assert result.upcoming_days[0][0:4] == (date(2026, 8, 31), 0, 0, 1)
        engine.dispose()
