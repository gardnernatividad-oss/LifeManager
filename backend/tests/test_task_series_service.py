import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Category, Project, TaskSeries, TaskSeriesFrequency, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.task_series import TaskSeriesCreate, TaskSeriesUpdate
from app.services.task_series_service import (
    TaskSeriesCategoryInactiveError, TaskSeriesPermissionError, TaskSeriesRecurrenceValidationError,
    activate_task_series, create_task_series, deactivate_task_series, get_task_series,
    list_task_series, update_task_series,
)


class TaskSeriesServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db=MagicMock(spec=Session); self.workspace_id=uuid.uuid4(); self.user=User(id=uuid.uuid4())
        self.start=datetime(2026,7,20,12,tzinfo=timezone.utc)
        self.membership=WorkspaceMember(workspace_id=self.workspace_id,user_id=self.user.id,role=WorkspaceRole.MEMBER)
    def member(self, value: object=...): return patch("app.services.task_series_service.get_workspace_membership", return_value=self.membership if value is ... else value)
    def series(self, **changes: object) -> TaskSeries:
        data=dict(id=uuid.uuid4(),workspace_id=self.workspace_id,created_by_id=self.user.id,category_id=None,project_id=None,title="Daily",description=None,timezone="America/Lima",frequency=TaskSeriesFrequency.DAILY,interval=1,weekdays=None,month_day=None,starts_at=self.start,ends_at=None,is_active=True)
        data.update(changes); return TaskSeries(**data)

    def test_create_all_shapes_associations_and_no_commit(self) -> None:
        category=Category(id=uuid.uuid4(),workspace_id=self.workspace_id,name="C",normalized_name="c",is_active=True)
        project=Project(id=uuid.uuid4(),workspace_id=self.workspace_id,name="P",normalized_name="p",is_active=True)
        cases=(("daily",None,None),("weekly",[1,3],None),("monthly",None,15))
        for frequency,weekdays,month_day in cases:
            self.db.reset_mock(); self.db.scalar.side_effect=[category,project]
            with self.subTest(frequency=frequency), self.member():
                series=create_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user,series_in=TaskSeriesCreate(title="Series",timezone="America/Lima",frequency=frequency,weekdays=weekdays,month_day=month_day,starts_at=self.start,category_id=category.id,project_id=project.id))
            self.assertTrue(series.is_active); self.assertEqual((series.category_id,series.project_id),(category.id,project.id))
            self.db.add.assert_called_once(); self.db.flush.assert_called_once(); self.db.commit.assert_not_called()

    def test_create_rejects_inactive_association_and_nonmember(self) -> None:
        category=Category(id=uuid.uuid4(),workspace_id=self.workspace_id,name="C",normalized_name="c",is_active=False); self.db.scalar.return_value=category
        with self.member(), self.assertRaises(TaskSeriesCategoryInactiveError): create_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user,series_in=TaskSeriesCreate(title="S",timezone="America/Lima",frequency="daily",starts_at=self.start,category_id=category.id))
        with self.member(None), self.assertRaises(TaskSeriesPermissionError): list_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user)

    def test_merged_update_strict_transition_and_inactive_edit(self) -> None:
        series=self.series(frequency=TaskSeriesFrequency.WEEKLY,weekdays=[1,3],is_active=False,category_id=uuid.uuid4()); self.db.scalar.return_value=series
        with self.member(), self.assertRaises(TaskSeriesRecurrenceValidationError): update_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,series_in=TaskSeriesUpdate(frequency="daily"))
        self.db.scalar.return_value=series
        with self.member(): result=update_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,series_in=TaskSeriesUpdate(frequency="daily",weekdays=None,description="Edited"))
        self.assertEqual(result.frequency,TaskSeriesFrequency.DAILY); self.assertIsNone(result.weekdays); self.assertEqual(result.description,"Edited")

    def test_list_filters_order_total_and_get_inactive(self) -> None:
        category=Category(id=uuid.uuid4(),workspace_id=self.workspace_id,name="C",normalized_name="c",is_active=False)
        project=Project(id=uuid.uuid4(),workspace_id=self.workspace_id,name="P",normalized_name="p",is_active=False)
        expected=[self.series(is_active=False,category_id=category.id,project_id=project.id)]
        self.db.scalar.side_effect=[category,project,1]; self.db.scalars.return_value.all.return_value=expected
        with self.member(): result,total=list_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user,is_active=False,category_id=category.id,project_id=project.id)
        self.assertEqual((result,total),(expected,1)); self.assertIn("ORDER BY task_series.is_active DESC, task_series.title, task_series.created_at, task_series.id",str(self.db.scalars.call_args.args[0]))
        self.db.scalar.side_effect=None; self.db.scalar.return_value=expected[0]
        with self.member(): self.assertIs(get_task_series(self.db,workspace_id=self.workspace_id,series_id=expected[0].id,current_user=self.user),expected[0])

    def test_lifecycle_is_idempotent_without_task_writes(self) -> None:
        series=self.series(); self.db.scalar.return_value=series
        with self.member(): deactivate_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user)
        self.assertFalse(series.is_active); self.db.flush.assert_called_once()
        self.db.reset_mock(); self.db.scalar.return_value=series
        with self.member(): deactivate_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user)
        self.db.flush.assert_not_called()
        with self.member(): activate_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user)
        self.assertTrue(series.is_active); self.db.add.assert_not_called(); self.db.commit.assert_not_called()


if __name__ == "__main__": unittest.main()
