import unittest
import uuid

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Task, TaskOutcome, TaskSeries, TaskSeriesFrequency, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.services.task_series_service import TaskSeriesPermissionError
from app.services.task_series_sync_service import TaskSeriesSyncInactiveError, synchronize_task_series


class TaskSeriesSyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db=MagicMock(spec=Session);self.workspace_id=uuid.uuid4();self.user=User(id=uuid.uuid4());self.now=datetime(2026,7,22,12,tzinfo=timezone.utc)
        self.membership=WorkspaceMember(workspace_id=self.workspace_id,user_id=self.user.id,role=WorkspaceRole.MEMBER)
    def member(self,value:object=...):return patch("app.services.task_series_sync_service.get_workspace_membership",return_value=self.membership if value is ... else value)
    def series(self,**changes:object)->TaskSeries:
        data=dict(id=uuid.uuid4(),workspace_id=self.workspace_id,created_by_id=self.user.id,category_id=None,project_id=None,title="New title",description="New description",timezone="America/Lima",frequency=TaskSeriesFrequency.DAILY,interval=1,weekdays=None,month_day=None,starts_at=self.now+timedelta(days=1,hours=2),ends_at=None,is_active=True)
        data.update(changes);return TaskSeries(**data)
    def task(self,series:TaskSeries,scheduled_at:datetime,**changes:object)->Task:
        data=dict(id=uuid.uuid4(),workspace_id=self.workspace_id,created_by_id=self.user.id,category_id=None,project_id=None,task_series_id=series.id,title="Old",description="Old",scheduled_at=scheduled_at,outcome=None,resolved_at=None,created_at=self.now-timedelta(days=5),updated_at=self.now-timedelta(days=5));data.update(changes);return Task(**data)
    def rows(self,items:list[Task])->MagicMock:
        result=MagicMock();result.all.return_value=items;return result

    def test_metadata_update_delete_obsolete_and_create_missing(self)->None:
        series=self.series(category_id=uuid.uuid4(),project_id=uuid.uuid4());valid_time=series.starts_at;obsolete_time=valid_time+timedelta(hours=1);existing=[self.task(series,valid_time),self.task(series,obsolete_time)]
        self.db.scalar.return_value=series;self.db.scalars.return_value=self.rows(existing)
        with self.member(),patch("app.services.task_series_sync_service._utc_now",return_value=self.now):result=synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=self.now,window_end=self.now+timedelta(days=3))
        self.assertEqual(len(result.updated_tasks),1);self.assertEqual(result.updated_tasks[0].title,"New title");self.assertEqual((result.updated_tasks[0].category_id,result.updated_tasks[0].project_id),(series.category_id,series.project_id));self.assertEqual(result.deleted_task_ids,[existing[1].id]);self.assertEqual(len(result.created_tasks),1)
        self.db.delete.assert_called_once_with(existing[1]);self.db.commit.assert_not_called();self.db.rollback.assert_not_called()

    def test_historical_terminal_and_manual_tasks_are_immutable(self)->None:
        series=self.series();historical=self.task(series,self.now-timedelta(days=1));completed=self.task(series,self.now+timedelta(days=1),outcome=TaskOutcome.COMPLETED,resolved_at=self.now);cancelled=self.task(series,self.now+timedelta(days=2),outcome=TaskOutcome.CANCELLED,resolved_at=self.now)
        self.db.scalar.return_value=series;self.db.scalars.return_value=self.rows([historical,completed,cancelled])
        with self.member(),patch("app.services.task_series_sync_service._utc_now",return_value=self.now):result=synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=self.now-timedelta(days=2),window_end=self.now+timedelta(days=2))
        self.assertEqual(result.updated_tasks,[]);self.db.delete.assert_not_called()
        statement=str(self.db.scalars.call_args.args[0]);self.assertIn("tasks.task_series_id",statement)
        self.assertTrue(all(task.title=="Old" for task in (historical,completed,cancelled)))

    def test_daily_weekly_monthly_timezone_and_dst_desired_sets(self)->None:
        cases=(
            (self.series(),self.now,self.now+timedelta(days=4),3),
            (self.series(frequency=TaskSeriesFrequency.WEEKLY,weekdays=[3],starts_at=datetime(2026,7,23,14,tzinfo=timezone.utc)),self.now,self.now+timedelta(days=10),2),
            (self.series(frequency=TaskSeriesFrequency.MONTHLY,month_day=31,starts_at=datetime(2026,7,31,14,tzinfo=timezone.utc)),self.now,datetime(2026,11,1,tzinfo=timezone.utc),3),
            (self.series(timezone="America/New_York",starts_at=datetime(2026,10,31,13,tzinfo=timezone.utc)),datetime(2026,10,30,tzinfo=timezone.utc),datetime(2026,11,3,tzinfo=timezone.utc),3),
        )
        for series,start,end,count in cases:
            self.db.reset_mock();self.db.scalar.return_value=series;self.db.scalars.return_value=self.rows([])
            with self.subTest(frequency=series.frequency,timezone=series.timezone),self.member(),patch("app.services.task_series_sync_service._utc_now",return_value=start-timedelta(seconds=1)):result=synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=start,window_end=end)
            self.assertEqual(len(result.created_tasks),count)
            if series.timezone=="America/New_York":self.assertEqual([task.scheduled_at.hour for task in result.created_tasks],[13,14,14])

    def test_idempotent_inactive_associations_authorization_and_window(self)->None:
        series=self.series(category_id=uuid.uuid4(),project_id=uuid.uuid4());existing=self.task(series,series.starts_at,title=series.title,description=series.description,category_id=series.category_id,project_id=series.project_id)
        self.db.scalar.side_effect=[series,series.category_id,series.project_id];self.db.scalars.return_value=self.rows([existing])
        with self.member(),patch("app.services.task_series_sync_service._utc_now",return_value=self.now):result=synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=self.now,window_end=self.now+timedelta(days=2))
        self.assertEqual((result.created_tasks,result.updated_tasks,result.deleted_task_ids),([],[],[]));self.db.add_all.assert_called_once_with([])
        series.is_active=False;self.db.reset_mock();self.db.scalar.side_effect=None;self.db.scalar.return_value=series
        with self.member(),self.assertRaises(TaskSeriesSyncInactiveError):synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=self.now,window_end=self.now)
        with self.member(None),self.assertRaises(TaskSeriesPermissionError):synchronize_task_series(self.db,workspace_id=self.workspace_id,series_id=series.id,current_user=self.user,window_start=self.now,window_end=self.now)


if __name__=="__main__":unittest.main()
