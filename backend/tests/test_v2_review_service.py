import uuid

from datetime import date
from unittest.mock import MagicMock

from app.services.v2_review import get_global_review


def test_global_review_builds_three_read_only_assignment_queries() -> None:
    db = MagicMock()
    db.execute.side_effect = [MagicMock(**{"all.return_value": []}) for _ in range(3)]
    user_id = uuid.uuid4()
    result = get_global_review(db, user_id=user_id, local_date=date(2026, 8, 28))
    assert result.tasks == result.pending_items == result.project_stages == []
    sql = [str(call.args[0]) for call in db.execute.call_args_list]
    assert "tasks.responsible_user_id" in sql[0] and "tasks.result IS NULL" in sql[0]
    assert "LEFT OUTER JOIN master_tasks" in sql[0]
    assert "pending_items.responsible_user_id" in sql[1] and "pending_items.is_active IS true" in sql[1]
    assert "project_stages.responsible_user_id" in sql[2] and "projects.is_active IS true" in sql[2]
    assert all("workspace_members.status" in statement and "workspaces.lifecycle" in statement for statement in sql)
    db.add.assert_not_called(); db.delete.assert_not_called(); db.flush.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_not_called()
