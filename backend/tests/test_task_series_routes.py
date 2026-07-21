import unittest
import uuid

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import TaskSeries, TaskSeriesFrequency, User
from app.services.task_series_service import TaskSeriesNotFoundError, TaskSeriesPermissionError, TaskSeriesRecurrenceValidationError


class TaskSeriesRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db=MagicMock(spec=Session); self.user=User(id=uuid.uuid4(),is_active=True); self.workspace_id=uuid.uuid4(); self.series_id=uuid.uuid4(); self.now=datetime.now(timezone.utc)
        app.dependency_overrides[get_db]=lambda:self.db; app.dependency_overrides[get_current_user]=lambda:self.user; self.client=TestClient(app)
    def tearDown(self) -> None: self.client.close(); app.dependency_overrides.clear()
    @property
    def collection(self)->str:return f"/api/v1/workspaces/{self.workspace_id}/task-series"
    @property
    def detail(self)->str:return f"{self.collection}/{self.series_id}"
    def series(self,**changes:object)->TaskSeries:
        data=dict(id=self.series_id,workspace_id=self.workspace_id,created_by_id=self.user.id,category_id=None,project_id=None,title="Daily",description=None,timezone="America/Lima",frequency=TaskSeriesFrequency.DAILY,interval=1,weekdays=None,month_day=None,starts_at=self.now,ends_at=None,is_active=True,created_at=self.now,updated_at=self.now);data.update(changes);return TaskSeries(**data)

    def test_create_commits_refreshes_and_serializes(self)->None:
        series=self.series()
        with patch("app.api.v1.task_series.task_series_service.create_task_series",return_value=series): response=self.client.post(self.collection,json={"title":"Daily","timezone":"America/Lima","frequency":"daily","starts_at":self.now.isoformat()})
        self.assertEqual(response.status_code,201);self.assertEqual(response.json()["frequency"],"daily");self.db.commit.assert_called_once();self.db.refresh.assert_called_once_with(series)

    def test_list_filters_get_patch_and_lifecycle(self)->None:
        category_id=uuid.uuid4();project_id=uuid.uuid4();series=self.series()
        with patch("app.api.v1.task_series.task_series_service.list_task_series",return_value=([series],1)) as service: response=self.client.get(f"{self.collection}?is_active=false&category_id={category_id}&project_id={project_id}")
        self.assertEqual(response.status_code,200);service.assert_called_once_with(self.db,workspace_id=self.workspace_id,current_user=self.user,is_active=False,category_id=category_id,project_id=project_id)
        with patch("app.api.v1.task_series.task_series_service.get_task_series",return_value=series):self.assertEqual(self.client.get(self.detail).status_code,200)
        with patch("app.api.v1.task_series.task_series_service.update_task_series",return_value=series):self.assertEqual(self.client.patch(self.detail,json={"description":None}).status_code,200)
        for action in ("activate","deactivate"):
            self.db.reset_mock()
            with patch(f"app.api.v1.task_series.task_series_service.{action}_task_series",return_value=series):response=self.client.post(f"{self.detail}/{action}")
            self.assertEqual(response.status_code,200);self.db.commit.assert_called_once()

    def test_error_mappings_auth_validation_and_no_extra_routes(self)->None:
        for error,status in ((TaskSeriesNotFoundError("Task series not found"),404),(TaskSeriesPermissionError("Workspace access denied"),403),(TaskSeriesRecurrenceValidationError("invalid recurrence"),409)):
            self.db.reset_mock()
            with patch("app.api.v1.task_series.task_series_service.update_task_series",side_effect=error):response=self.client.patch(self.detail,json={"description":"x"})
            self.assertEqual(response.status_code,status);self.db.rollback.assert_called_once()
        invalid=self.client.post(self.collection,json={"title":"Bad","timezone":"bad","frequency":"weekly","starts_at":self.now.isoformat()});self.assertEqual(invalid.status_code,422)
        app.dependency_overrides.pop(get_current_user);self.assertEqual(self.client.get(self.collection).status_code,401);app.dependency_overrides[get_current_user]=lambda:self.user
        self.assertEqual(self.client.delete(self.detail).status_code,405)
        paths=app.openapi()["paths"];self.assertNotIn("delete",paths["/api/v1/workspaces/{workspace_id}/task-series/{series_id}"])
        self.assertFalse(any("generate" in path or "occurrence" in path for path in paths))


if __name__=="__main__":unittest.main()
