import uuid

from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import ActivityMaster, MasterTask
from app.schemas.v2_catalog import CategoryCreate, CatalogItemCreate, CatalogItemUpdate
from app.services.v2_catalog import (
    CatalogCategoryUnavailableError,
    CatalogNameConflictError,
    CatalogNotFoundError,
    CatalogVersionConflictError,
    create_category,
    create_item,
    set_category_active,
    update_item,
)
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_catalog_constraints_lifecycle_and_workspace_isolation_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Catalog PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            user_id = uuid.uuid4()
            workspace_a, workspace_b = uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name) VALUES (:id,:email,'hash','Ana','Test')"), {"id": user_id, "email": f"catalog-{user_id}@example.test"})
            for workspace_id, name in ((workspace_a, "A"), (workspace_b, "B")):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,'SHARED',:owner)"), {"id": workspace_id, "name": name, "owner": user_id})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": user_id})
            db.commit()

            category_a = create_category(db, workspace_id=workspace_a, category_in=CategoryCreate(name="  Tecnología "))
            db.commit()
            category_b = create_category(db, workspace_id=workspace_b, category_in=CategoryCreate(name="TECNOLOGÍA"))
            db.commit()
            assert category_a.normalized_name == category_b.normalized_name

            with pytest.raises(CatalogNameConflictError):
                create_category(db, workspace_id=workspace_a, category_in=CategoryCreate(name="tecnología"))
            db.rollback()

            with pytest.raises(CatalogNotFoundError):
                create_item(db, model=MasterTask, workspace_id=workspace_a, item_in=CatalogItemCreate(name="Foreign", category_id=category_b.id))
            db.rollback()

            category_a = db.get(type(category_a), category_a.id)
            master = create_item(db, model=MasterTask, workspace_id=workspace_a, item_in=CatalogItemCreate(name="Leer", category_id=category_a.id))
            activity = create_item(db, model=ActivityMaster, workspace_id=workspace_a, item_in=CatalogItemCreate(name="Caminar", category_id=category_a.id))
            db.commit()
            assert master.workspace_id == activity.workspace_id == workspace_a

            set_category_active(db, workspace_id=workspace_a, category_id=category_a.id, expected_version=category_a.lock_version, active=False)
            db.commit()
            with pytest.raises(CatalogCategoryUnavailableError):
                create_item(db, model=MasterTask, workspace_id=workspace_a, item_in=CatalogItemCreate(name="Otro", category_id=category_a.id))
            db.rollback()

            with pytest.raises(CatalogVersionConflictError):
                update_item(db, model=MasterTask, workspace_id=workspace_a, item_id=master.id, item_in=CatalogItemUpdate(name="Cambio", lock_version=999))
            db.rollback()
        engine.dispose()
