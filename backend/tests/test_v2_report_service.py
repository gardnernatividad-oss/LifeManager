import uuid

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.v2_report import get_activity_report, get_report_summary


def test_report_summary_uses_one_workspace_scoped_aggregate_query() -> None:
    db = MagicMock()
    db.execute.return_value.one.return_value = SimpleNamespace(
        tasks=4,
        pending_items=3,
        projects=2,
        activities=1,
    )
    workspace_id = uuid.uuid4()
    category_id = uuid.uuid4()
    responsible_id = uuid.uuid4()

    result = get_report_summary(
        db,
        workspace_id=workspace_id,
        timezone_name="America/Lima",
        date_from=date(2026, 8, 1),
        date_until=date(2026, 8, 31),
        category_id=category_id,
        responsible_user_id=responsible_id,
    )

    assert (result.tasks, result.pending_items, result.projects, result.activities, result.total) == (4, 3, 2, 1, 10)
    db.execute.assert_called_once()
    sql = str(db.execute.call_args.args[0])
    assert sql.count("SELECT count(") >= 4
    for table in ("tasks", "pending_items", "projects", "activities"):
        assert table in sql
    assert sql.count("workspace_id") >= 4
    assert "master_tasks.category_id" in sql
    assert "tasks.custom_category_id" in sql
    assert "activity_masters.category_id" in sql
    assert "activities.custom_category_id" in sql
    assert "tasks.responsible_user_id" in sql
    assert "pending_items.responsible_user_id" in sql
    assert "projects.leader_user_id" in sql
    assert "activities.organizer_user_id" in sql


def test_report_summary_supports_open_periods_and_timezone_activity_boundaries() -> None:
    db = MagicMock()
    db.execute.return_value.one.return_value = SimpleNamespace(tasks=0, pending_items=0, projects=0, activities=0)

    get_report_summary(
        db,
        workspace_id=uuid.uuid4(),
        timezone_name="America/New_York",
        date_from=date(2026, 3, 8),
    )

    statement = db.execute.call_args.args[0]
    parameters = statement.compile().params
    datetimes = [value for value in parameters.values() if hasattr(value, "tzinfo")]
    assert any(value.isoformat() == "2026-03-08T00:00:00-05:00" for value in datetimes)
    sql = str(statement)
    assert "activities.starts_at >=" in sql
    assert "activities.starts_at <" not in sql


def test_activity_report_uses_sql_aggregation_and_local_dst_boundaries() -> None:
    metric = SimpleNamespace(total_count=0, scheduled_count=0, cancelled_count=0, total_duration_minutes=0, average_duration_minutes=None)
    empty = MagicMock(); empty.all.return_value = []
    summary = MagicMock(); summary.one.return_value = metric
    db = MagicMock(); db.execute.side_effect = [summary, empty, empty, empty, empty]

    result = get_activity_report(
        db, workspace_id=uuid.uuid4(), timezone_name="America/New_York",
        date_from=date(2026, 3, 8), date_until=date(2026, 3, 8), custom_activities=True,
    )

    assert result["summary"]["total_count"] == 0
    assert len(db.execute.call_args_list) == 5
    sql = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
    assert "activity_masters" in sql and "categories" in sql and "users" in sql
    assert "extract(epoch from" in sql.lower() and "activities.ends_at - activities.starts_at" in sql
    assert "activities.activity_master_id IS NULL" in sql
    parameters = [value for call in db.execute.call_args_list for value in call.args[0].compile().params.values()]
    assert any(getattr(value, "isoformat", lambda: "")() == "2026-03-08T00:00:00-05:00" for value in parameters)
    assert any(getattr(value, "isoformat", lambda: "")() == "2026-03-09T00:00:00-04:00" for value in parameters)
