import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import GenerationBatch, Task, User, Workspace, WorkspaceMember
from app.models.enums import TaskResult
from app.schemas.v2_task import RecurringTaskCreate, TaskCreate, TaskUpdate
from app.services.v2_task import TaskConflictError, TaskReferenceUnavailableError, create_recurring_tasks, create_task, resolve_task, update_task
from app.services.v2_workspace import WorkspaceAccess
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_task_lifecycle_and_integrity_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Task PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            owner_id, member_id, foreign_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            workspace_id, foreign_workspace = uuid.uuid4(), uuid.uuid4()
            for user_id, email in ((owner_id, "owner@test.local"), (member_id, "member@test.local"), (foreign_id, "foreign@test.local")):
                db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at) VALUES (:id,:email,'hash','Test','User','ACTIVE',now())"), {"id": user_id, "email": email})
            for current, name, owner in ((workspace_id, "Shared", owner_id), (foreign_workspace, "Foreign", foreign_id)):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,'SHARED',:owner)"), {"id": current, "name": name, "owner": owner})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": current, "user": owner})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": member_id})
            category_id, foreign_category = uuid.uuid4(), uuid.uuid4()
            master_id, foreign_master = uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Casa','casa')"), {"id": category_id, "workspace": workspace_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Otra','otra')"), {"id": foreign_category, "workspace": foreign_workspace})
            db.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Comprar','comprar')"), {"id": master_id, "workspace": workspace_id, "category": category_id})
            db.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Ajena','ajena')"), {"id": foreign_master, "workspace": foreign_workspace, "category": foreign_category})
            db.commit()
            owner, member = db.get(User, owner_id), db.get(User, member_id)
            workspace, membership = db.get(Workspace, workspace_id), db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == owner_id))
            access = WorkspaceAccess(workspace=workspace, membership=membership)

            task = create_task(db, access=access, actor=owner, task_in=TaskCreate(master_task_id=master_id, planned_date=date(2026, 9, 1), responsible_user_id=member_id))
            db.commit()
            assert task.generation_batch_id is None and task.responsible_user_id == member_id
            with pytest.raises(TaskReferenceUnavailableError):
                create_task(db, access=access, actor=owner, task_in=TaskCreate(master_task_id=foreign_master, planned_date=date(2026, 9, 1), responsible_user_id=member_id))
            db.rollback()
            with pytest.raises(TaskConflictError):
                create_task(db, access=access, actor=owner, task_in=TaskCreate(master_task_id=master_id, planned_date=date(2026, 9, 1), responsible_user_id=member_id))
            db.rollback()
            second = create_task(db, access=access, actor=owner, task_in=TaskCreate(master_task_id=master_id, planned_date=date(2026, 9, 1), responsible_user_id=owner_id))
            db.commit()
            task = db.get(Task, task.id)
            update_task(db, access=access, task_id=task.id, task_in=TaskUpdate(planned_date=date(2026, 9, 2), lock_version=task.lock_version), local_date=date(2026, 8, 31))
            db.commit()
            task = db.get(Task, task.id)
            resolve_task(db, access=access, actor=member, task_id=task.id, expected_version=task.lock_version, result=TaskResult.COMPLETED, local_date=date(2026, 9, 2))
            db.commit()
            assert task.result == TaskResult.COMPLETED and task.resolved_by_user_id == member_id
            with pytest.raises(TaskConflictError):
                update_task(db, access=access, task_id=task.id, task_in=TaskUpdate(planned_date=date(2026, 9, 3), lock_version=task.lock_version), local_date=date(2026, 9, 2))
            db.rollback()
            assert second.responsible_user_id == owner_id

            standalone_collision = RecurringTaskCreate.model_validate({"master_task_id": str(master_id), "responsible_user_id": str(member_id), "recurrence": {"pattern": "DAILY", "date_from": "2026-09-02", "date_until": "2026-09-02"}})
            batches_before_collision = db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch))
            with pytest.raises(TaskConflictError):
                create_recurring_tasks(db, access=access, actor=owner, task_in=standalone_collision)
            db.rollback()
            assert db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch)) == batches_before_collision

            recurring = RecurringTaskCreate.model_validate({"master_task_id": str(master_id), "responsible_user_id": str(member_id), "recurrence": {"pattern": "MONTHLY", "date_from": "2027-01-29", "date_until": "2027-03-31", "month_days": [29, 30, 31]}})
            occurrences = create_recurring_tasks(db, access=access, actor=owner, task_in=recurring)
            db.commit()
            assert [item.planned_date for item in occurrences] == [date(2027, 1, 29), date(2027, 1, 30), date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 29), date(2027, 3, 30), date(2027, 3, 31)]
            batch_ids = {item.generation_batch_id for item in occurrences}
            assert len(batch_ids) == 1
            batch = db.get(GenerationBatch, batch_ids.pop())
            assert batch.entity_type == "TASK" and batch.timezone is None

            batches_before = db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch))
            tasks_before = db.scalar(sa.select(sa.func.count()).select_from(Task))
            with pytest.raises(TaskConflictError):
                create_recurring_tasks(db, access=access, actor=owner, task_in=recurring)
            db.rollback()
            assert db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch)) == batches_before
            assert db.scalar(sa.select(sa.func.count()).select_from(Task)) == tasks_before

        barrier = Barrier(2)
        concurrent_request = RecurringTaskCreate.model_validate({"master_task_id": str(master_id), "responsible_user_id": str(member_id), "recurrence": {"pattern": "DAILY", "date_from": "2028-01-01", "date_until": "2028-01-02"}})

        def submit_same_recurrence() -> str:
            with Session(engine) as concurrent_db:
                concurrent_owner = concurrent_db.get(User, owner_id)
                concurrent_workspace = concurrent_db.get(Workspace, workspace_id)
                concurrent_membership = concurrent_db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == owner_id))
                barrier.wait()
                try:
                    create_recurring_tasks(concurrent_db, access=WorkspaceAccess(workspace=concurrent_workspace, membership=concurrent_membership), actor=concurrent_owner, task_in=concurrent_request)
                    concurrent_db.commit()
                    return "created"
                except TaskConflictError:
                    concurrent_db.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(executor.map(lambda _: submit_same_recurrence(), range(2)))
        assert outcomes == ["conflict", "created"]
        with Session(engine) as verification_db:
            assert verification_db.scalar(sa.select(sa.func.count()).select_from(Task).where(Task.planned_date.in_([date(2028, 1, 1), date(2028, 1, 2)]))) == 2
            batch_ids = verification_db.scalars(sa.select(Task.generation_batch_id).where(Task.planned_date.in_([date(2028, 1, 1), date(2028, 1, 2)]))).all()
            assert len(set(batch_ids)) == 1
        engine.dispose()
