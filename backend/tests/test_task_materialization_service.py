import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import TaskSeries, TaskSeriesFrequency, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.services.task_materialization_service import TaskMaterializationValidationError, materialize_task_series, materialize_workspace_task_series
from app.services.task_series_service import TaskSeriesPermissionError


class TaskMaterializationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db=MagicMock(spec=Session); self.workspace_id=uuid.uuid4(); self.user=User(id=uuid.uuid4())
        self.membership=WorkspaceMember(workspace_id=self.workspace_id,user_id=self.user.id,role=WorkspaceRole.MEMBER)
    def series(self,**changes:object)->TaskSeries:
        data=dict(id=uuid.uuid4(),workspace_id=self.workspace_id,created_by_id=self.user.id,category_id=None,project_id=None,title="Recurring",description="Copy",timezone="America/Lima",frequency=TaskSeriesFrequency.DAILY,interval=1,weekdays=None,month_day=None,starts_at=datetime(2026,1,1,14,tzinfo=timezone.utc),ends_at=None,is_active=True)
        data.update(changes);return TaskSeries(**data)
    def member(self,value:object=...):return patch("app.services.task_materialization_service.get_workspace_membership",return_value=self.membership if value is ... else value)
    def empty_existing(self)->MagicMock:
        result=MagicMock();result.all.return_value=[];return result

    def test_daily_generation_copies_fields_and_never_commits(self)->None:
        series=self.series(category_id=uuid.uuid4(),project_id=uuid.uuid4());self.db.scalar.side_effect=[series,series.category_id,series.project_id];self.db.scalars.return_value=self.empty_existing()
        with self.member():tasks=materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=datetime(2026,1,1,tzinfo=timezone.utc),window_end=datetime(2026,1,3,23,tzinfo=timezone.utc))
        self.assertEqual(len(tasks),3)
        self.assertTrue(all((t.workspace_id,t.created_by_id,t.category_id,t.project_id,t.task_series_id,t.title,t.description,t.outcome,t.resolved_at)==(series.workspace_id,series.created_by_id,series.category_id,series.project_id,series.id,series.title,series.description,None,None) for t in tasks))
        self.db.add_all.assert_called_once_with(tasks);self.db.flush.assert_called_once();self.db.commit.assert_not_called();self.db.rollback.assert_not_called()

    def test_weekly_and_monthly_generation(self)->None:
        weekly=self.series(frequency=TaskSeriesFrequency.WEEKLY,weekdays=[0,2],starts_at=datetime(2026,1,5,14,tzinfo=timezone.utc))
        monthly=self.series(frequency=TaskSeriesFrequency.MONTHLY,month_day=31,starts_at=datetime(2026,1,31,14,tzinfo=timezone.utc))
        for series,start,end,expected in ((weekly,datetime(2026,1,5,tzinfo=timezone.utc),datetime(2026,1,11,23,tzinfo=timezone.utc),2),(monthly,datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,4,30,23,tzinfo=timezone.utc),2)):
            self.db.reset_mock();self.db.scalar.return_value=series;self.db.scalars.return_value=self.empty_existing()
            with self.subTest(frequency=series.frequency),self.member():tasks=materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=start,window_end=end)
            self.assertEqual(len(tasks),expected)

    def test_dst_preserves_local_wall_clock_time(self)->None:
        series=self.series(timezone="America/New_York",starts_at=datetime(2026,3,7,14,tzinfo=timezone.utc));self.db.scalar.return_value=series;self.db.scalars.return_value=self.empty_existing()
        with self.member():tasks=materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=datetime(2026,3,7,tzinfo=timezone.utc),window_end=datetime(2026,3,9,23,tzinfo=timezone.utc))
        self.assertEqual([t.scheduled_at.hour for t in tasks],[14,13,13])

    def test_idempotency_inactive_validation_membership_and_manual_tasks(self)->None:
        series=self.series();candidate=series.starts_at;self.db.scalar.return_value=series
        existing=self.empty_existing();existing.all.return_value=[candidate];self.db.scalars.return_value=existing
        with self.member():self.assertEqual(materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=candidate,window_end=candidate),[])
        self.db.add_all.assert_called_once_with([])
        series.is_active=False;self.db.reset_mock();self.db.scalar.return_value=series
        with self.member():self.assertEqual(materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=candidate,window_end=candidate),[])
        self.db.add_all.assert_not_called();self.db.query.assert_not_called()
        with self.assertRaises(TaskMaterializationValidationError):materialize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=candidate,window_end=candidate.replace(year=2025))
        with self.member(None),self.assertRaises(TaskSeriesPermissionError):materialize_workspace_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user,window_start=candidate,window_end=candidate)

    def test_workspace_materializes_all_active_series(self)->None:
        items=[self.series(),self.series()];series_result=MagicMock();series_result.all.return_value=items
        self.db.scalars.side_effect=[series_result,self.empty_existing(),self.empty_existing()]
        with self.member():tasks=materialize_workspace_task_series(self.db,workspace_id=self.workspace_id,current_user=self.user,window_start=datetime(2026,1,1,tzinfo=timezone.utc),window_end=datetime(2026,1,1,23,tzinfo=timezone.utc))
        self.assertEqual(len(tasks),2)


if __name__=="__main__":unittest.main()
