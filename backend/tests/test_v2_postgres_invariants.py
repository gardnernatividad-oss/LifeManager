"""PostgreSQL-only V2 invariants; requires an explicitly provisioned local schema."""

import os
import uuid
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.base import Base


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("PostgreSQL V2 integration tests refuse non-local hosts")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.fail("PostgreSQL V2 integration tests refuse non-allowlisted databases")
    return url


@pytest.fixture
def connection():
    engine = sa.create_engine(_local_test_url())
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()
    engine.dispose()


def _user(connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    connection.execute(sa.text("""
        INSERT INTO users (id,email,hashed_password,first_name,last_name)
        VALUES (:id,:email,'hash','Test','User')
    """), {"id": user_id, "email": f"{user_id}@example.test"})
    return user_id


def _workspace_with_owner(connection, owner_id: uuid.UUID, kind: str = "SHARED") -> uuid.UUID:
    workspace_id = uuid.uuid4()
    connection.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Test',:kind,:owner)"), {"id": workspace_id, "kind": kind, "owner": owner_id})
    connection.execute(sa.text("INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"), {"id": uuid.uuid4(), "workspace": workspace_id, "user": owner_id})
    connection.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    connection.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))
    return workspace_id


def test_owner_requires_active_membership_at_constraint_boundary(connection) -> None:
    owner_id = _user(connection)
    connection.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Invalid','SHARED',:owner)"), {"id": uuid.uuid4(), "owner": owner_id})
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_personal_workspace_is_unique_per_owner(connection) -> None:
    owner_id = _user(connection)
    _workspace_with_owner(connection, owner_id, "PERSONAL")
    nested = connection.begin_nested()
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Second','PERSONAL',:owner)"), {"id": uuid.uuid4(), "owner": owner_id})
    nested.rollback()


def test_task_responsible_must_be_a_member_of_the_same_workspace(connection) -> None:
    owner_a, owner_b = _user(connection), _user(connection)
    workspace_a = _workspace_with_owner(connection, owner_a)
    _workspace_with_owner(connection, owner_b)
    category_id, master_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'C','c')"), {"id": category_id, "workspace": workspace_a})
    connection.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'M','m')"), {"id": master_id, "workspace": workspace_a, "category": category_id})
    nested = connection.begin_nested()
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("""
            INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id)
            VALUES (:id,:workspace,:master,:responsible,CURRENT_DATE,:creator)
        """), {"id": uuid.uuid4(), "workspace": workspace_a, "master": master_id, "responsible": owner_b, "creator": owner_a})
    nested.rollback()


def test_task_occurrence_identity_is_unique(connection) -> None:
    owner = _user(connection)
    workspace = _workspace_with_owner(connection, owner)
    category_id, master_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'C','c')"), {"id": category_id, "workspace": workspace})
    connection.execute(sa.text("INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) VALUES (:id,:workspace,:category,'M','m')"), {"id": master_id, "workspace": workspace, "category": category_id})
    params = {"workspace": workspace, "master": master_id, "responsible": owner, "creator": owner}
    connection.execute(sa.text("INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id) VALUES (:id,:workspace,:master,:responsible,CURRENT_DATE,:creator)"), {**params, "id": uuid.uuid4()})
    nested = connection.begin_nested()
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id) VALUES (:id,:workspace,:master,:responsible,CURRENT_DATE,:creator)"), {**params, "id": uuid.uuid4()})
    nested.rollback()


def test_activity_participant_must_be_a_member_of_the_same_workspace(connection) -> None:
    organizer, foreign_user = _user(connection), _user(connection)
    workspace = _workspace_with_owner(connection, organizer)
    _workspace_with_owner(connection, foreign_user)
    category_id, activity_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'C','c')"), {"id": category_id, "workspace": workspace})
    connection.execute(sa.text("""
        INSERT INTO activities (id,workspace_id,organizer_user_id,title,custom_category_id,starts_at,ends_at)
        VALUES (:id,:workspace,:organizer,'Activity',:category,now() + interval '1 day',now() + interval '2 days')
    """), {"id": activity_id, "workspace": workspace, "organizer": organizer, "category": category_id})
    nested = connection.begin_nested()
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("""
            INSERT INTO activity_participants (id,activity_id,workspace_id,user_id)
            VALUES (:id,:activity,:workspace,:user)
        """), {"id": uuid.uuid4(), "activity": activity_id, "workspace": workspace, "user": foreign_user})
    nested.rollback()


def test_frozen_migration_schema_matches_current_v2_metadata(connection) -> None:
    inspector = sa.inspect(connection)
    assert set(inspector.get_table_names(schema="public")) - {"alembic_version"} == set(Base.metadata.tables)
    for table_name, table in Base.metadata.tables.items():
        database_columns = {
            column["name"]: column for column in inspector.get_columns(table_name, schema="public")
        }
        assert set(database_columns) == set(table.columns.keys())
        for column in table.columns:
            assert database_columns[column.name]["nullable"] is column.nullable

        model_names = {
            constraint.name for constraint in table.constraints if constraint.name is not None
        }
        database_names = {
            item["name"] for item in inspector.get_unique_constraints(table_name, schema="public")
        } | {
            item["name"] for item in inspector.get_check_constraints(table_name, schema="public")
        } | {
            item["name"] for item in inspector.get_foreign_keys(table_name, schema="public")
        }
        assert model_names <= database_names
        assert {index.name for index in table.indexes} == {
            item["name"] for item in inspector.get_indexes(table_name, schema="public")
            if not item.get("duplicates_constraint")
        }

    trigger_names = set(connection.execute(sa.text(
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
    )).scalars())
    assert {
        "ct_workspaces_owner_active_member",
        "ct_workspace_members_owner_active_member",
        "ct_tasks_batch_entity_type",
        "ct_activities_batch_entity_type",
    } <= trigger_names
    function_names = set(connection.execute(sa.text(
        "SELECT proname FROM pg_proc JOIN pg_namespace ON pg_namespace.oid=pronamespace "
        "WHERE nspname='public'"
    )).scalars())
    assert {
        "lifemanager_smallint_array_unique_in_range",
        "lifemanager_assert_workspace_owner_active_member",
        "lifemanager_assert_occurrence_batch_entity_type",
    } <= function_names
