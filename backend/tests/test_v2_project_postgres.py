import uuid

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import Project, ProjectLeaderHistory, User, Workspace, WorkspaceMember
from app.schemas.v2_project import ProjectCreate, ProjectUpdate
from app.schemas.v2_project_stage import ProjectStageCreate, ProjectStageUpdate
from app.services.v2_project import ProjectConflictError, ProjectNotFoundError, ProjectReferenceUnavailableError, create_project, deactivate_project, get_project, list_projects, reactivate_project, update_project
from app.services.v2_project_stage import ProjectStageConflictError, ProjectStageNotFoundError, ProjectStageReferenceUnavailableError, create_project_stage, get_project_stage, project_stage_summary, stage_projection, update_project_stage, update_project_stage_progress
from app.services.v2_workspace import WorkspaceAccess
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_project_lifecycle_authority_and_concurrency_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Project PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            owner_id, member_id, foreign_id, disabled_id = (uuid.uuid4() for _ in range(4))
            personal_id, shared_id, foreign_workspace_id = (uuid.uuid4() for _ in range(3))
            users = ((owner_id, "owner@test.local", "ACTIVE"), (member_id, "member@test.local", "ACTIVE"), (foreign_id, "foreign@test.local", "ACTIVE"), (disabled_id, "disabled@test.local", "DISABLED"))
            for user_id, email, account_status in users:
                db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at) VALUES (:id,:email,'hash','Test','User',:status,now())"), {"id": user_id, "email": email, "status": account_status})
            for workspace_id, owner, name, kind in ((personal_id, owner_id, "Personal", "PERSONAL"), (shared_id, owner_id, "Shared", "SHARED"), (foreign_workspace_id, foreign_id, "Foreign", "SHARED")):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,:kind,:owner)"), {"id": workspace_id, "name": name, "kind": kind, "owner": owner})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": owner})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": shared_id, "user": member_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": shared_id, "user": disabled_id})
            category_id, foreign_category_id, inactive_category_id = (uuid.uuid4() for _ in range(3))
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Casa','casa')"), {"id": category_id, "workspace": shared_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Otra','otra')"), {"id": foreign_category_id, "workspace": foreign_workspace_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name,is_active) VALUES (:id,:workspace,'Vieja','vieja',false)"), {"id": inactive_category_id, "workspace": shared_id})
            personal_category_id = uuid.uuid4()
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Personal','personal')"), {"id": personal_category_id, "workspace": personal_id})
            db.commit()

            owner, member = db.get(User, owner_id), db.get(User, member_id)
            personal = db.get(Workspace, personal_id); shared = db.get(Workspace, shared_id)
            personal_access = WorkspaceAccess(personal, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == personal_id, WorkspaceMember.user_id == owner_id)))
            member_access = WorkspaceAccess(shared, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == shared_id, WorkspaceMember.user_id == member_id)))
            personal_project = create_project(db, access=personal_access, actor=owner, project_in=ProjectCreate(category_id=personal_category_id, leader_user_id=foreign_id, name="Personal"))
            shared_project = create_project(db, access=member_access, actor=member, project_in=ProjectCreate(category_id=category_id, leader_user_id=owner_id, name="Mudanza"))
            db.commit()
            assert personal_project.leader_user_id == owner_id
            assert shared_project.created_by_user_id == member_id and shared_project.is_active is True
            assert db.scalar(sa.select(sa.func.count()).select_from(ProjectLeaderHistory).where(ProjectLeaderHistory.project_id == shared_project.id)) == 1

            first = create_project_stage(db, access=member_access, actor=member, project_id=shared_project.id, stage_in=ProjectStageCreate(name="Empacar", responsible_user_id=owner_id, position=0, weight="40.00", planned_date="2026-09-10", project_lock_version=shared_project.lock_version))
            second = create_project_stage(db, access=member_access, actor=member, project_id=shared_project.id, stage_in=ProjectStageCreate(name="Transportar", responsible_user_id=member_id, position=1, weight="60.00", planned_date="2026-09-12", project_lock_version=shared_project.lock_version))
            db.commit()
            incomplete = project_stage_summary([first], local_date=first.planned_date)
            assert incomplete["weights_complete"] is False and incomplete["progress"] is None
            complete = project_stage_summary([first, second], local_date=first.planned_date)
            assert complete["weights_complete"] is True and complete["progress"] == 0 and complete["state"] == "NO_INICIADO"
            with pytest.raises(ProjectStageReferenceUnavailableError):
                update_project_stage(db, access=member_access, project_id=shared_project.id, stage_id=first.id, stage_in=ProjectStageUpdate(responsible_user_id=foreign_id, lock_version=first.lock_version, project_lock_version=shared_project.lock_version))
            db.rollback(); member = db.get(User, member_id); shared = db.get(Workspace, shared_id); member_access = WorkspaceAccess(shared, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == shared_id, WorkspaceMember.user_id == member_id))); shared_project = db.get(Project, shared_project.id); first = get_project_stage(db, workspace_id=shared_id, project_id=shared_project.id, stage_id=first.id); second = get_project_stage(db, workspace_id=shared_id, project_id=shared_project.id, stage_id=second.id)
            update_project_stage_progress(db, access=member_access, project_id=shared_project.id, stage_id=first.id, progress=50, expected_version=first.lock_version, project_version=shared_project.lock_version, local_date=first.planned_date)
            update_project_stage_progress(db, access=member_access, project_id=shared_project.id, stage_id=second.id, progress=100, expected_version=second.lock_version, project_version=shared_project.lock_version, local_date=second.planned_date)
            db.commit()
            weighted = project_stage_summary([first, second], local_date=second.planned_date)
            assert weighted["progress"] == 80 and weighted["state"] == "EN_PROCESO" and second.completion_date == second.planned_date
            assert stage_projection(second, local_date=second.planned_date)[:3] == ("FINALIZADA", "A_TIEMPO", 0)
            with pytest.raises(ProjectStageConflictError):
                update_project_stage_progress(db, access=member_access, project_id=shared_project.id, stage_id=second.id, progress=90, expected_version=second.lock_version, project_version=shared_project.lock_version, local_date=second.planned_date)
            with pytest.raises(ProjectStageNotFoundError):
                get_project_stage(db, workspace_id=foreign_workspace_id, project_id=shared_project.id, stage_id=first.id)
            db.rollback(); member = db.get(User, member_id); shared = db.get(Workspace, shared_id); member_access = WorkspaceAccess(shared, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == shared_id, WorkspaceMember.user_id == member_id))); shared_project = db.get(Project, shared_project.id)

            for bad_category, bad_leader in ((foreign_category_id, owner_id), (inactive_category_id, owner_id), (category_id, foreign_id), (category_id, disabled_id)):
                with pytest.raises(ProjectReferenceUnavailableError):
                    create_project(db, access=member_access, actor=member, project_in=ProjectCreate(category_id=bad_category, leader_user_id=bad_leader, name="Inválido"))
                db.rollback()
                member = db.get(User, member_id); shared = db.get(Workspace, shared_id)
                member_access = WorkspaceAccess(shared, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == shared_id, WorkspaceMember.user_id == member_id)))

            shared_project = get_project(db, workspace_id=shared_id, project_id=shared_project.id)
            before_update = shared_project.lock_version
            update_project(db, access=member_access, actor=member, project_id=shared_project.id, project_in=ProjectUpdate(leader_user_id=member_id, name="Mudanza familiar", description="Plan", lock_version=shared_project.lock_version))
            db.commit()
            assert shared_project.leader_user_id == member_id and shared_project.lock_version == before_update + 1
            assert db.scalar(sa.select(sa.func.count()).select_from(ProjectLeaderHistory).where(ProjectLeaderHistory.project_id == shared_project.id)) == 2
            deactivate_project(db, access=member_access, project_id=shared_project.id, expected_version=shared_project.lock_version); db.commit()
            assert shared_project.is_active is False
            reactivate_project(db, access=member_access, project_id=shared_project.id, expected_version=shared_project.lock_version); db.commit()
            assert shared_project.is_active is True
            rows, total = list_projects(db, workspace_id=shared_id, page=1, page_size=25, is_active=True, category_id=category_id, leader_user_id=member_id, search="FAMILIAR")
            assert total == 1 and rows[0][0].id == shared_project.id
            with pytest.raises(ProjectNotFoundError):
                get_project(db, workspace_id=foreign_workspace_id, project_id=shared_project.id)

            race_id, race_version = shared_project.id, shared_project.lock_version
            def race_edit(name: str) -> str:
                with Session(engine) as concurrent_db:
                    concurrent_actor = concurrent_db.get(User, member_id)
                    concurrent_workspace = concurrent_db.get(Workspace, shared_id)
                    concurrent_membership = concurrent_db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == shared_id, WorkspaceMember.user_id == member_id))
                    try:
                        update_project(concurrent_db, access=WorkspaceAccess(concurrent_workspace, concurrent_membership), actor=concurrent_actor, project_id=race_id, project_in=ProjectUpdate(name=name, lock_version=race_version))
                        concurrent_db.commit(); return "updated"
                    except ProjectConflictError:
                        concurrent_db.rollback(); return "conflict"
            with ThreadPoolExecutor(max_workers=2) as executor:
                assert sorted(executor.map(race_edit, ("Nombre A", "Nombre B"))) == ["conflict", "updated"]
            db.expire_all()
            assert db.get(Project, race_id).lock_version == race_version + 1
        engine.dispose()
