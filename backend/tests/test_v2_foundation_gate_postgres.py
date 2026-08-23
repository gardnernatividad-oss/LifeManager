"""Release-gate checks for V2 PostgreSQL constraints and rollback behavior."""

import os
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


def _local_test_url() -> str:
    url = os.getenv("LIFEMANAGER_V2_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("LIFEMANAGER_V2_TEST_DATABASE_URL is not configured")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("V2 foundation gate refuses non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.fail("V2 foundation gate requires an allowlisted disposable database")
    return url


@pytest.fixture
def engine():
    value = sa.create_engine(_local_test_url())
    yield value
    value.dispose()


@pytest.fixture
def connection(engine):
    with engine.connect() as value:
        transaction = value.begin()
        yield value
        transaction.rollback()


def _user(connection, label: str) -> uuid.UUID:
    identifier = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO users (id,email,hashed_password,first_name,last_name) "
        "VALUES (:id,:email,'fixture-hash','Gate','User')"
    ), {"id": identifier, "email": f"{label}-{identifier}@example.test"})
    return identifier


def _workspace(connection, owner: uuid.UUID, label: str, *, kind: str = "SHARED") -> uuid.UUID:
    identifier = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,:name,:kind,:owner)"
    ), {"id": identifier, "name": label, "kind": kind, "owner": owner})
    _member(connection, identifier, owner)
    connection.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    connection.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))
    return identifier


def _member(connection, workspace: uuid.UUID, user: uuid.UUID) -> None:
    connection.execute(sa.text(
        "INSERT INTO workspace_members (id,workspace_id,user_id) VALUES (:id,:workspace,:user)"
    ), {"id": uuid.uuid4(), "workspace": workspace, "user": user})


def _category(connection, workspace: uuid.UUID, name: str = "Gate Category") -> uuid.UUID:
    identifier = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,:name,:normalized)"
    ), {"id": identifier, "workspace": workspace, "name": name, "normalized": name.casefold()})
    return identifier


def _master(connection, workspace: uuid.UUID, category: uuid.UUID) -> uuid.UUID:
    identifier = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO master_tasks (id,workspace_id,category_id,name,normalized_name) "
        "VALUES (:id,:workspace,:category,'Gate Master','gate master')"
    ), {"id": identifier, "workspace": workspace, "category": category})
    return identifier


@contextmanager
def _rejected(connection, label: str = "constraint"):
    nested = connection.begin_nested()
    try:
        try:
            yield
        except IntegrityError:
            pass
        else:
            pytest.fail(f"{label} did not raise IntegrityError")
    finally:
        nested.rollback()


def test_atomic_workspace_owner_membership_and_duplicate_membership(connection) -> None:
    owner = _user(connection, "owner")
    workspace = _workspace(connection, owner, "Atomic")
    assert connection.scalar(sa.text(
        "SELECT count(*) FROM workspace_members WHERE workspace_id=:workspace AND user_id=:owner"
    ), {"workspace": workspace, "owner": owner}) == 1

    with _rejected(connection):
        _member(connection, workspace, owner)


def test_same_workspace_constraints_reject_foreign_users(connection) -> None:
    owner_a, owner_b = _user(connection, "owner-a"), _user(connection, "owner-b")
    workspace_a = _workspace(connection, owner_a, "A")
    _workspace(connection, owner_b, "B")
    category = _category(connection, workspace_a)
    project = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO projects (id,workspace_id,category_id,leader_user_id,name,created_by_user_id) "
        "VALUES (:id,:workspace,:category,:owner,'Gate Project',:owner)"
    ), {"id": project, "workspace": workspace_a, "category": category, "owner": owner_a})
    activity = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO activities (id,workspace_id,organizer_user_id,title,custom_category_id,starts_at,ends_at) "
        "VALUES (:id,:workspace,:owner,'Gate Activity',:category,now()+interval '1 hour',now()+interval '2 hours')"
    ), {"id": activity, "workspace": workspace_a, "owner": owner_a, "category": category})

    statements = [
        ("INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,created_by_user_id) VALUES (:id,:workspace,:category,:foreign,'Pending',CURRENT_DATE,:owner)", {}),
        ("INSERT INTO projects (id,workspace_id,category_id,leader_user_id,name,created_by_user_id) VALUES (:id,:workspace,:category,:foreign,'Foreign leader',:owner)", {}),
        ("INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date) VALUES (:id,:workspace,:project,:foreign,'Stage',0,100,CURRENT_DATE)", {"project": project}),
        ("INSERT INTO activities (id,workspace_id,organizer_user_id,title,custom_category_id,starts_at,ends_at) VALUES (:id,:workspace,:foreign,'Foreign organizer',:category,now()+interval '1 hour',now()+interval '2 hours')", {}),
        ("INSERT INTO activity_participants (id,activity_id,workspace_id,user_id) VALUES (:id,:activity,:workspace,:foreign)", {"activity": activity}),
    ]
    common = {"workspace": workspace_a, "category": category, "foreign": owner_b, "owner": owner_a}
    for statement, extra in statements:
        with _rejected(connection):
            connection.execute(sa.text(statement), {**common, **extra, "id": uuid.uuid4()})


def test_uniqueness_and_cross_workspace_catalog_rules(connection) -> None:
    owner, responsible = _user(connection, "owner"), _user(connection, "responsible")
    workspace = _workspace(connection, owner, "Shared")
    _member(connection, workspace, responsible)
    other_owner = _user(connection, "other")
    other_workspace = _workspace(connection, other_owner, "Other")
    category = _category(connection, workspace, "Personal")
    _category(connection, other_workspace, "Personal")
    master = _master(connection, workspace, category)
    task_sql = sa.text(
        "INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id) "
        "VALUES (:id,:workspace,:master,:responsible,CURRENT_DATE,:owner)"
    )
    connection.execute(task_sql, {"id": uuid.uuid4(), "workspace": workspace, "master": master, "responsible": owner, "owner": owner})
    connection.execute(task_sql, {"id": uuid.uuid4(), "workspace": workspace, "master": master, "responsible": responsible, "owner": owner})
    with _rejected(connection):
        connection.execute(task_sql, {"id": uuid.uuid4(), "workspace": workspace, "master": master, "responsible": owner, "owner": owner})
    with _rejected(connection):
        _category(connection, workspace, "Personal")

    activity = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO activities (id,workspace_id,organizer_user_id,title,custom_category_id,starts_at,ends_at) "
        "VALUES (:id,:workspace,:owner,'Unique Activity',:category,now()+interval '1 hour',now()+interval '2 hours')"
    ), {"id": activity, "workspace": workspace, "owner": owner, "category": category})
    participant_sql = sa.text("INSERT INTO activity_participants (id,activity_id,workspace_id,user_id) VALUES (:id,:activity,:workspace,:user)")
    reminder_sql = sa.text("INSERT INTO activity_reminders (id,activity_id,workspace_id,user_id,minutes_before) VALUES (:id,:activity,:workspace,:user,15)")
    params = {"activity": activity, "workspace": workspace, "user": responsible}
    connection.execute(participant_sql, {**params, "id": uuid.uuid4()})
    connection.execute(reminder_sql, {**params, "id": uuid.uuid4()})
    with _rejected(connection):
        connection.execute(participant_sql, {**params, "id": uuid.uuid4()})
    with _rejected(connection):
        connection.execute(reminder_sql, {**params, "id": uuid.uuid4()})


def test_key_check_constraints_reject_invalid_states(connection) -> None:
    owner = _user(connection, "owner")
    workspace = _workspace(connection, owner, "Checks")
    category = _category(connection, workspace)
    master = _master(connection, workspace, category)
    project = uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO projects (id,workspace_id,category_id,leader_user_id,name,created_by_user_id) "
        "VALUES (:id,:workspace,:category,:owner,'Checks Project',:owner)"
    ), {"id": project, "workspace": workspace, "category": category, "owner": owner})

    invalid = [
        ("progress below zero", "INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:owner,'Low',CURRENT_DATE,-1,:owner)", {}),
        ("progress above 100", "INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:owner,'High',CURRENT_DATE,101,:owner)", {}),
        ("zero stage weight", "INSERT INTO project_stages (id,workspace_id,project_id,responsible_user_id,name,position,weight,planned_date) VALUES (:id,:workspace,:project,:owner,'Weight',0,0,CURRENT_DATE)", {"project": project}),
        ("zero lock version", "INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,created_by_user_id,lock_version) VALUES (:id,:workspace,:master,:owner,CURRENT_DATE,:owner,0)", {"master": master}),
        ("invalid activity range", "INSERT INTO activities (id,workspace_id,organizer_user_id,title,custom_category_id,starts_at,ends_at) VALUES (:id,:workspace,:owner,'Time',:category,now(),now())", {}),
        ("invalid recurrence shape", "INSERT INTO generation_batches (id,workspace_id,entity_type,pattern,date_from,date_until,created_by_user_id) VALUES (:id,:workspace,'TASK','WEEKLY',CURRENT_DATE,CURRENT_DATE,:owner)", {}),
        ("invalid task resolution", "INSERT INTO tasks (id,workspace_id,master_task_id,responsible_user_id,planned_date,result,created_by_user_id) VALUES (:id,:workspace,:master,:owner,CURRENT_DATE,'COMPLETED',:owner)", {"master": master}),
        ("invalid completion state", "INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) VALUES (:id,:workspace,:category,:owner,'Complete',CURRENT_DATE,100,:owner)", {}),
        ("blank notification body", "INSERT INTO notifications (id,recipient_user_id,notification_type,title,body) VALUES (:id,:owner,'TASK_ASSIGNED','Title','   ')", {}),
    ]
    common = {"workspace": workspace, "category": category, "owner": owner}
    for label, statement, extra in invalid:
        with _rejected(connection, label):
            connection.execute(sa.text(statement), {**common, **extra, "id": uuid.uuid4()})


def test_history_survives_current_state_mutation(connection) -> None:
    owner = _user(connection, "owner")
    workspace = _workspace(connection, owner, "History")
    category = _category(connection, workspace)
    item, history = uuid.uuid4(), uuid.uuid4()
    connection.execute(sa.text(
        "INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,progress,created_by_user_id) "
        "VALUES (:id,:workspace,:category,:owner,'History item',CURRENT_DATE,20,:owner)"
    ), {"id": item, "workspace": workspace, "category": category, "owner": owner})
    connection.execute(sa.text(
        "INSERT INTO pending_item_history (id,pending_item_id,workspace_id,actor_user_id,progress,event_type) "
        "VALUES (:id,:item,:workspace,:owner,20,'TRACKING')"
    ), {"id": history, "item": item, "workspace": workspace, "owner": owner})
    connection.execute(sa.text("UPDATE pending_items SET progress=60 WHERE id=:item"), {"item": item})
    assert connection.scalar(sa.text("SELECT progress FROM pending_item_history WHERE id=:id"), {"id": history}) == 20


def test_deferred_owner_failure_rolls_back_full_transaction(engine) -> None:
    owner, workspace = uuid.uuid4(), uuid.uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(sa.text(
            "INSERT INTO users (id,email,hashed_password,first_name,last_name) VALUES (:id,:email,'hash','Rollback','Owner')"
        ), {"id": owner, "email": f"rollback-{owner}@example.test"})
        connection.execute(sa.text(
            "INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Invalid owner','SHARED',:owner)"
        ), {"id": workspace, "owner": owner})
        with pytest.raises(IntegrityError):
            transaction.commit()
        transaction.rollback()
    with engine.connect() as verification:
        assert verification.scalar(sa.text("SELECT count(*) FROM workspaces WHERE id=:id"), {"id": workspace}) == 0
        assert verification.scalar(sa.text("SELECT count(*) FROM users WHERE id=:id"), {"id": owner}) == 0


def test_composite_fk_failure_rolls_back_related_attempt(engine) -> None:
    owner, foreign, workspace, category, pending = (uuid.uuid4() for _ in range(5))
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(sa.text(
            "INSERT INTO users (id,email,hashed_password,first_name,last_name) VALUES (:id,:email,'hash','Rollback','Owner'),(:foreign,:foreign_email,'hash','Foreign','User')"
        ), {"id": owner, "email": f"owner-{owner}@example.test", "foreign": foreign, "foreign_email": f"foreign-{foreign}@example.test"})
        connection.execute(sa.text("INSERT INTO workspaces (id,name,kind,owner_user_id) VALUES (:id,'Rollback','SHARED',:owner)"), {"id": workspace, "owner": owner})
        _member(connection, workspace, owner)
        connection.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
        connection.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))
        connection.execute(sa.text("INSERT INTO categories (id,workspace_id,name,normalized_name) VALUES (:id,:workspace,'Rollback','rollback')"), {"id": category, "workspace": workspace})
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO pending_items (id,workspace_id,category_id,responsible_user_id,name,planned_date,created_by_user_id) VALUES (:id,:workspace,:category,:foreign,'Invalid',CURRENT_DATE,:owner)"
            ), {"id": pending, "workspace": workspace, "category": category, "foreign": foreign, "owner": owner})
        transaction.rollback()
    with engine.connect() as verification:
        assert verification.scalar(sa.text("SELECT count(*) FROM categories WHERE id=:id"), {"id": category}) == 0
        assert verification.scalar(sa.text("SELECT count(*) FROM pending_items WHERE id=:id"), {"id": pending}) == 0
