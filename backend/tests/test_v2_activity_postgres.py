import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import Activity, ActivityParticipant, GenerationBatch, User, Workspace, WorkspaceMember
from app.schemas.v2_activity import ActivityCreate, ActivityUpdate, RecurringActivityCreate
from app.services.v2_activity import ActivityConflictError, ActivityReferenceUnavailableError, create_activity, create_recurring_activities, delete_activity, leave_activity, update_activity
from app.services.v2_calendar import list_my_calendar
from app.services.v2_workspace import WorkspaceAccess
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_activity_lifecycle_and_workspace_integrity_on_disposable_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("V2 Activity PostgreSQL gate requires local PostgreSQL")
    with disposable_postgres_database(source_url, database_name="lifemanager_v2_test", explicit_test_intent=True) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1"); monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True), "head")
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            owner_id, member_id, foreign_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            workspace_id, foreign_workspace_id = uuid.uuid4(), uuid.uuid4()
            for user_id, email in ((owner_id, "owner@test.local"), (member_id, "member@test.local"), (foreign_id, "foreign@test.local")):
                db.execute(sa.text("INSERT INTO users (id,email,hashed_password,first_name,last_name,account_status,email_verified_at) VALUES (:id,:email,'hash','Test','User','ACTIVE',now())"), {"id": user_id, "email": email})
            for identifier, owner, name in ((workspace_id, owner_id, "Shared"), (foreign_workspace_id, foreign_id, "Foreign")):
                db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,'SHARED',:owner)"), {"id": identifier, "name": name, "owner": owner})
                db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": identifier, "user": owner})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": member_id})
            category_id, foreign_category_id, master_id, foreign_master_id = (uuid.uuid4() for _ in range(4))
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Familia','familia')"), {"id": category_id, "workspace": workspace_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Otra','otra')"), {"id": foreign_category_id, "workspace": foreign_workspace_id})
            db.execute(sa.text("INSERT INTO activity_masters (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Reunión','reunión')"), {"id": master_id, "workspace": workspace_id, "category": category_id})
            db.execute(sa.text("INSERT INTO activity_masters (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Ajena','ajena')"), {"id": foreign_master_id, "workspace": foreign_workspace_id, "category": foreign_category_id})
            db.commit()
            actor = db.get(User, member_id); workspace = db.get(Workspace, workspace_id)
            access = WorkspaceAccess(workspace, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == member_id)))
            start = datetime.now(timezone.utc) + timedelta(days=2)
            created = create_activity(db, access=access, actor=actor, activity_in=ActivityCreate(activity_master_id=master_id, organizer_user_id=owner_id, participant_user_ids=[member_id], starts_at=start, ends_at=start + timedelta(hours=1)))
            db.commit(); db.refresh(created)
            assert created.workspace_id == workspace_id and created.title == "Reunión" and created.generation_batch_id is None
            assert db.scalar(sa.select(sa.func.count()).select_from(ActivityParticipant).where(ActivityParticipant.activity_id == created.id)) == 1
            with pytest.raises(ActivityReferenceUnavailableError):
                create_activity(db, access=access, actor=actor, activity_in=ActivityCreate(activity_master_id=foreign_master_id, organizer_user_id=owner_id, starts_at=start, ends_at=start + timedelta(hours=1)))
            db.rollback(); actor = db.get(User, member_id); workspace = db.get(Workspace, workspace_id); access = WorkspaceAccess(workspace, db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == member_id))); created = db.get(Activity, created.id)
            update_activity(db, access=access, activity_id=created.id, activity_in=ActivityUpdate(ends_at=start + timedelta(hours=2), participant_user_ids=[owner_id, member_id], lock_version=created.lock_version)); db.commit(); db.refresh(created)
            assert created.lock_version == 2 and db.scalar(sa.select(sa.func.count()).select_from(ActivityParticipant).where(ActivityParticipant.activity_id == created.id)) == 2
            leave_activity(db, access=access, actor=actor, activity_id=created.id, expected_version=created.lock_version); db.commit(); db.refresh(created)
            participant = db.scalar(sa.select(ActivityParticipant).where(ActivityParticipant.activity_id == created.id, ActivityParticipant.user_id == member_id))
            assert participant.calendar_status == "REMOVED" and created.lock_version == 3
            with pytest.raises(ActivityConflictError):
                delete_activity(db, access=access, activity_id=created.id, expected_version=2)
            db.rollback(); created = db.get(Activity, created.id); delete_activity(db, access=access, activity_id=created.id, expected_version=created.lock_version); db.commit()
            assert db.get(Activity, created.id) is None
            recurring = RecurringActivityCreate.model_validate({
                "activity_master_id": str(master_id), "organizer_user_id": str(owner_id),
                "participant_user_ids": [str(member_id)], "start_time": "09:00", "end_time": "10:00",
                "timezone": "America/Lima", "recurrence": {"pattern": "DAILY", "date_from": "2027-01-04", "date_until": "2027-01-05"},
            })
            generated = create_recurring_activities(db, access=access, actor=actor, activity_in=recurring); db.commit()
            assert len(generated) == 2 and len({item.generation_batch_id for item in generated}) == 1
            assert db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch)) == 1
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": foreign_workspace_id, "user": member_id})
            db.commit(); actor = db.get(User, member_id)
            foreign_access = WorkspaceAccess(db.get(Workspace, foreign_workspace_id), db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == foreign_workspace_id, WorkspaceMember.user_id == member_id)))
            foreign_activity = create_activity(db, access=foreign_access, actor=actor, activity_in=ActivityCreate(
                activity_master_id=foreign_master_id, organizer_user_id=foreign_id, participant_user_ids=[member_id],
                starts_at=datetime(2027, 1, 5, 14, tzinfo=timezone.utc), ends_at=datetime(2027, 1, 5, 16, tzinfo=timezone.utc),
            )); db.commit()
            personal_workspace_id, personal_category_id, personal_master_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            db.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Personal','PERSONAL',:owner)"), {"id": personal_workspace_id, "owner": member_id})
            db.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": personal_workspace_id, "user": member_id})
            db.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Personal','personal')"), {"id": personal_category_id, "workspace": personal_workspace_id})
            db.execute(sa.text("INSERT INTO activity_masters (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'Ejercicio','ejercicio')"), {"id": personal_master_id, "workspace": personal_workspace_id, "category": personal_category_id}); db.commit()
            personal_access = WorkspaceAccess(db.get(Workspace, personal_workspace_id), db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == personal_workspace_id, WorkspaceMember.user_id == member_id)))
            personal_activity = create_activity(db, access=personal_access, actor=actor, activity_in=ActivityCreate(
                activity_master_id=personal_master_id, starts_at=datetime(2027, 1, 4, 14, 45, tzinfo=timezone.utc), ends_at=datetime(2027, 1, 4, 15, 15, tzinfo=timezone.utc),
            )); db.commit()
            consolidated = list_my_calendar(db, user_id=member_id, range_start=datetime(2027, 1, 4, 14, 30, tzinfo=timezone.utc), range_end=datetime(2027, 1, 5, 15, tzinfo=timezone.utc), now=datetime(2026, 12, 31, tzinfo=timezone.utc))
            assert {item.activity.id for item in consolidated} == {generated[0].id, generated[1].id, foreign_activity.id, personal_activity.id}
            assert [(item.activity.starts_at, item.activity.ends_at, str(item.activity.id)) for item in consolidated] == sorted((item.activity.starts_at, item.activity.ends_at, str(item.activity.id)) for item in consolidated)
            withdrawn_activity = create_activity(db, access=foreign_access, actor=actor, activity_in=ActivityCreate(
                activity_master_id=foreign_master_id, organizer_user_id=foreign_id, participant_user_ids=[member_id],
                starts_at=datetime(2027, 1, 8, 14, tzinfo=timezone.utc), ends_at=datetime(2027, 1, 8, 15, tzinfo=timezone.utc),
            )); db.commit()
            foreign_participant = db.scalar(sa.select(ActivityParticipant).where(ActivityParticipant.activity_id == foreign_activity.id, ActivityParticipant.user_id == member_id))
            foreign_participant.calendar_status = "REMOVED"; foreign_participant.removed_at = datetime(2027, 1, 6, tzinfo=timezone.utc)
            withdrawn_participant = db.scalar(sa.select(ActivityParticipant).where(ActivityParticipant.activity_id == withdrawn_activity.id, ActivityParticipant.user_id == member_id))
            withdrawn_participant.calendar_status = "REMOVED"; withdrawn_participant.removed_at = datetime(2027, 1, 6, tzinfo=timezone.utc)
            foreign_membership = foreign_access.membership; foreign_membership.status = "LEFT"; foreign_membership.ended_at = datetime(2027, 1, 6, tzinfo=timezone.utc)
            foreign_access.workspace.lifecycle = "INACTIVE"; foreign_access.workspace.deactivated_at = datetime(2027, 1, 6, tzinfo=timezone.utc); db.commit()
            historical = list_my_calendar(db, user_id=member_id, range_start=datetime(2027, 1, 5, tzinfo=timezone.utc), range_end=datetime(2027, 1, 6, tzinfo=timezone.utc), now=datetime(2027, 1, 7, tzinfo=timezone.utc))
            assert {item.activity.id for item in historical} == {generated[1].id, foreign_activity.id}
            foreign_projection = next(item for item in historical if item.activity.id == foreign_activity.id)
            assert foreign_projection.can_edit is False and foreign_projection.can_leave_participation is False
            assert list_my_calendar(db, user_id=member_id, range_start=datetime(2027, 1, 8, tzinfo=timezone.utc), range_end=datetime(2027, 1, 9, tzinfo=timezone.utc), now=datetime(2027, 1, 7, tzinfo=timezone.utc)) == []
            with pytest.raises(ActivityConflictError):
                create_recurring_activities(db, access=access, actor=actor, activity_in=recurring)
            db.rollback()
            assert db.scalar(sa.select(sa.func.count()).select_from(Activity)) == 5
            assert db.scalar(sa.select(sa.func.count()).select_from(ActivityParticipant)) == 5
            assert db.scalar(sa.select(sa.func.count()).select_from(GenerationBatch)) == 1
            with pytest.raises(ActivityConflictError):
                create_activity(db, access=access, actor=actor, activity_in=ActivityCreate(
                    activity_master_id=master_id, organizer_user_id=owner_id,
                    starts_at=datetime(2027, 1, 4, 14, tzinfo=timezone.utc),
                    ends_at=datetime(2027, 1, 4, 15, tzinfo=timezone.utc),
                ))
            db.rollback()
            standalone_start = datetime(2027, 3, 1, 14, tzinfo=timezone.utc)
            standalone = create_activity(db, access=access, actor=actor, activity_in=ActivityCreate(
                activity_master_id=master_id, organizer_user_id=owner_id,
                starts_at=standalone_start, ends_at=standalone_start + timedelta(hours=1),
            )); db.commit()
            standalone_collision = RecurringActivityCreate.model_validate({
                "activity_master_id": str(master_id), "organizer_user_id": str(owner_id),
                "participant_user_ids": [], "start_time": "09:00", "end_time": "10:00",
                "timezone": "America/Lima", "recurrence": {"pattern": "DAILY", "date_from": "2027-03-01", "date_until": "2027-03-01"},
            })
            with pytest.raises(ActivityConflictError):
                create_recurring_activities(db, access=access, actor=actor, activity_in=standalone_collision)
            db.rollback()
        barrier = Barrier(2)
        concurrent_request = RecurringActivityCreate.model_validate({
            "activity_master_id": str(master_id), "organizer_user_id": str(owner_id),
            "participant_user_ids": [str(member_id)], "start_time": "11:00", "end_time": "12:00",
            "timezone": "America/Lima", "recurrence": {"pattern": "DAILY", "date_from": "2027-02-01", "date_until": "2027-02-02"},
        })

        def submit_same_recurrence() -> str:
            with Session(engine) as concurrent_db:
                concurrent_actor = concurrent_db.get(User, member_id)
                concurrent_workspace = concurrent_db.get(Workspace, workspace_id)
                membership = concurrent_db.scalar(sa.select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == member_id))
                barrier.wait()
                try:
                    create_recurring_activities(concurrent_db, access=WorkspaceAccess(concurrent_workspace, membership), actor=concurrent_actor, activity_in=concurrent_request)
                    concurrent_db.commit()
                    return "created"
                except ActivityConflictError:
                    concurrent_db.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(executor.map(lambda _: submit_same_recurrence(), range(2)))
        assert outcomes == ["conflict", "created"]
        with Session(engine) as verification_db:
            starts = [datetime(2027, 2, 1, 16, tzinfo=timezone.utc), datetime(2027, 2, 2, 16, tzinfo=timezone.utc)]
            assert verification_db.scalar(sa.select(sa.func.count()).select_from(Activity).where(Activity.starts_at.in_(starts))) == 2
            batch_ids = verification_db.scalars(sa.select(Activity.generation_batch_id).where(Activity.starts_at.in_(starts))).all()
            assert len(set(batch_ids)) == 1
        engine.dispose()
        config = alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True)
        command.downgrade(config, "e6f7a8b9c0d1")
        command.upgrade(config, "head")
        inspection_engine = sa.create_engine(target_url)
        try:
            assert "uq_activities_catalog_occurrence" in {index["name"] for index in sa.inspect(inspection_engine).get_indexes("activities")}
        finally:
            inspection_engine.dispose()
