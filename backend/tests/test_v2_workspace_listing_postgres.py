import uuid

from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_account, get_db
from app.db import session as db_session
from app.main import app
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, GlobalRole, MembershipStatus, WorkspaceKind, WorkspaceLifecycle
from tests.postgres_safety import alembic_config_for_test_database, disposable_postgres_database


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _user(label: str, *, admin: bool = False) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email=f"{label}-{uuid.uuid4()}@example.test",
        hashed_password="fixture-hash",
        first_name=label,
        last_name="Workspace",
        timezone="America/Lima",
        account_status=AccountStatus.ACTIVE,
        global_role=GlobalRole.GLOBAL_ADMIN if admin else None,
        email_verified_at=now,
        status_changed_at=now,
    )


def test_real_postgres_workspace_listing_serializes_persisted_string_enums(monkeypatch: pytest.MonkeyPatch) -> None:
    source_url = make_url(db_session.DATABASE_URL)
    if source_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Workspace listing PostgreSQL regression requires local PostgreSQL")
    with disposable_postgres_database(
        source_url,
        database_name="lifemanager_test",
        explicit_test_intent=True,
    ) as target_url:
        monkeypatch.setenv("LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET", "1")
        monkeypatch.setenv("LIFEMANAGER_ENV", "testing")
        command.upgrade(
            alembic_config_for_test_database(target_url, backend_root=BACKEND_ROOT, explicit_test_intent=True),
            "head",
        )
        engine = sa.create_engine(target_url)
        with Session(engine) as db:
            admin = _user("admin", admin=True)
            shared_owner = _user("shared-owner")
            outsider = _user("outsider")
            now = datetime.now(timezone.utc)
            personal = Workspace(id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL, owner_user_id=admin.id)
            shared = Workspace(id=uuid.uuid4(), name="Familia", kind=WorkspaceKind.SHARED, owner_user_id=shared_owner.id)
            inactive = Workspace(id=uuid.uuid4(), name="Archivado", kind=WorkspaceKind.SHARED, owner_user_id=shared_owner.id, lifecycle=WorkspaceLifecycle.INACTIVE, deactivated_at=now)
            foreign = Workspace(id=uuid.uuid4(), name="Ajeno", kind=WorkspaceKind.SHARED, owner_user_id=outsider.id)
            db.add_all([admin, shared_owner, outsider, personal, shared, inactive, foreign])
            db.flush()
            db.add_all([
                WorkspaceMember(workspace_id=personal.id, user_id=admin.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=shared.id, user_id=shared_owner.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=shared.id, user_id=admin.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=inactive.id, user_id=shared_owner.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=inactive.id, user_id=admin.id, status=MembershipStatus.ACTIVE),
                WorkspaceMember(workspace_id=foreign.id, user_id=outsider.id, status=MembershipStatus.ACTIVE),
            ])
            db.commit()
            db.expire_all()
            persisted_admin = db.get(User, admin.id)
            assert persisted_admin is not None

            def override_db():
                yield db

            app.dependency_overrides[get_db] = override_db
            app.dependency_overrides[get_current_account] = lambda: persisted_admin
            try:
                response = TestClient(app).get("/api/v2/workspaces")
            finally:
                app.dependency_overrides.clear()

            assert response.status_code == 200
            assert [(item["name"], item["kind"]) for item in response.json()] == [
                ("Personal", "PERSONAL"),
                ("Familia", "SHARED"),
            ]
            assert all(set(item) == {
                "id", "name", "kind", "lifecycle", "visible_role", "can_manage",
                "can_delete", "timezone", "color", "icon", "lock_version",
            } for item in response.json())
        engine.dispose()
