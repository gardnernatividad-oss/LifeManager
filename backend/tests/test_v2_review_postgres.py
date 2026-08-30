import uuid

from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import PendingItem, PendingItemHistory, Project, ProjectStage, ProjectStageHistory, Task, User
from app.schemas.v2_review import ReviewPendingItemChange, ReviewProjectStageChange, ReviewTaskChange
from app.services.v2_review import ReviewConflictError, get_global_review, save_review_pending_items, save_review_project_stages, save_review_tasks
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
            db.execute(sa.text("INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date,progress) VALUES (:id,:workspace,:project,:responsible,'Etapa',1,100,:planned,50)"), {"id": stage_id, "workspace": second_workspace, "project": project_id, "responsible": user_id, "planned": date(2026, 8, 26)})
            db.commit()
            result = get_global_review(db, user_id=user_id, local_date=date(2026, 8, 28))
            assert [row[0].id for row in result.tasks] == [task_ids[1], task_ids[0]]
            assert [row[0].id for row in result.pending_items] == [pending_id]
            assert [row[0].id for row in result.project_stages] == [stage_id]
            assert not db.new and not db.dirty and not db.deleted
            assert get_global_review(db, user_id=admin_id, local_date=date(2026, 8, 28)) == type(result)(tasks=[], pending_items=[], project_stages=[])

            custom_task_id = uuid.uuid4()
            db.execute(sa.text("INSERT INTO tasks (id,workspace_id,custom_name,custom_category_id,responsible_user_id,planned_date,created_by_user_id) VALUES (:id,:workspace,'Otra tarea real',:category,:responsible,:planned,:creator)"), {"id": custom_task_id, "workspace": active_workspace, "category": category_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 28), "creator": user_id})
            db.commit()
            custom_selection = get_global_review(db, user_id=user_id, local_date=date(2026, 8, 28))
            assert any(task.id == custom_task_id and master is None for task, master, _ in custom_selection.tasks)

            actor = db.get(User, user_id)
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id,status) VALUES (:id,:workspace,:user,'ACTIVE')"), {"id": uuid.uuid4(), "workspace": active_workspace, "user": other_id})
            valid_task_id, invalid_task_id = uuid.UUID(int=1001), uuid.UUID(int=1002)
            db.execute(sa.text("INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id) VALUES (:id,:workspace,:master,:responsible,:planned,:creator)"), [
                {"id": valid_task_id, "workspace": active_workspace, "master": master_ids[active_workspace], "responsible": user_id, "planned": date(2026, 8, 25), "creator": user_id},
                {"id": invalid_task_id, "workspace": active_workspace, "master": master_ids[active_workspace], "responsible": other_id, "planned": date(2026, 8, 25), "creator": user_id},
            ])
            valid_pending_id, invalid_pending_id = uuid.UUID(int=2001), uuid.UUID(int=2002)
            db.execute(sa.text("INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:responsible,:name,:planned,10,:creator)"), [
                {"id": valid_pending_id, "workspace": active_workspace, "category": category_ids[active_workspace], "responsible": user_id, "name": "Pending válido", "planned": date(2026, 8, 28), "creator": user_id},
                {"id": invalid_pending_id, "workspace": active_workspace, "category": category_ids[active_workspace], "responsible": other_id, "name": "Pending ajeno", "planned": date(2026, 8, 28), "creator": user_id},
            ])
            valid_stage_id, invalid_stage_id = uuid.UUID(int=3001), uuid.UUID(int=3002)
            db.execute(sa.text("INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date,progress) VALUES (:id,:workspace,:project,:responsible,:name,:position,:weight,:planned,10)"), [
                {"id": valid_stage_id, "workspace": second_workspace, "project": project_id, "responsible": user_id, "name": "Etapa válida", "position": 2, "weight": 50, "planned": date(2026, 8, 28)},
                {"id": invalid_stage_id, "workspace": second_workspace, "project": project_id, "responsible": other_id, "name": "Etapa ajena", "position": 3, "weight": 50, "planned": date(2026, 8, 28)},
            ])
            db.commit()
            project_version = db.get(Project, project_id).lock_version

            with pytest.raises(ReviewConflictError):
                save_review_tasks(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewTaskChange(task_id=valid_task_id, result="COMPLETED", lock_version=1), ReviewTaskChange(task_id=invalid_task_id, result="COMPLETED", lock_version=1)])
            db.rollback()
            assert db.get(Task, valid_task_id).result is None

            with pytest.raises(ReviewConflictError):
                save_review_pending_items(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewPendingItemChange(pending_item_id=valid_pending_id, progress=50, lock_version=1), ReviewPendingItemChange(pending_item_id=invalid_pending_id, progress=50, lock_version=1)])
            db.rollback()
            assert db.get(PendingItem, valid_pending_id).progress == 10
            assert db.scalar(sa.select(sa.func.count()).select_from(PendingItemHistory).where(PendingItemHistory.pending_item_id == valid_pending_id)) == 0

            with pytest.raises(ReviewConflictError):
                save_review_project_stages(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewProjectStageChange(stage_id=valid_stage_id, progress="50.25", lock_version=1, project_lock_version=project_version), ReviewProjectStageChange(stage_id=invalid_stage_id, progress="50.25", lock_version=1, project_lock_version=project_version)])
            db.rollback()
            assert db.get(ProjectStage, valid_stage_id).progress == 10
            assert db.scalar(sa.select(sa.func.count()).select_from(ProjectStageHistory).where(ProjectStageHistory.project_stage_id == valid_stage_id)) == 0
            assert db.get(Project, project_id).lock_version == project_version

            for operation in (
                lambda: save_review_tasks(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewTaskChange(task_id=valid_task_id, result="COMPLETED", lock_version=999)]),
                lambda: save_review_pending_items(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewPendingItemChange(pending_item_id=valid_pending_id, progress=20, lock_version=999)]),
                lambda: save_review_project_stages(db, actor=actor, local_date=date(2026, 8, 28), changes=[ReviewProjectStageChange(stage_id=valid_stage_id, progress="20.25", lock_version=999, project_lock_version=project_version)]),
            ):
                with pytest.raises(ReviewConflictError):
                    operation()
                db.rollback()
        engine.dispose()
