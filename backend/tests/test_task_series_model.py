import unittest

from sqlalchemy import CheckConstraint, inspect

from app.models import Category, Project, Task, TaskSeries, TaskSeriesFrequency, User, Workspace
from app.models.base import Base


class TaskSeriesModelTests(unittest.TestCase):
    def test_fields_constraints_indexes_and_no_task_relationship(self) -> None:
        self.assertEqual(TaskSeries.__tablename__, "task_series")
        self.assertIs(Base.metadata.tables["task_series"], TaskSeries.__table__)
        expected = {"id", "workspace_id", "created_by_id", "category_id", "project_id", "title", "description", "timezone", "frequency", "interval", "weekdays", "month_day", "starts_at", "ends_at", "is_active", "created_at", "updated_at"}
        self.assertEqual(set(TaskSeries.__table__.columns.keys()), expected)
        self.assertEqual([x.value for x in TaskSeriesFrequency], ["daily", "weekly", "monthly"])
        checks = {c.name for c in TaskSeries.__table__.constraints if isinstance(c, CheckConstraint)}
        self.assertEqual(checks, {"ck_task_series_title_not_blank", "ck_task_series_interval_range", "ck_task_series_recurrence_shape", "ck_task_series_end_after_start"})
        indexes = {i.name: tuple(c.name for c in i.columns) for i in TaskSeries.__table__.indexes}
        self.assertEqual(indexes["ix_task_series_workspace_id_is_active_title"], ("workspace_id", "is_active", "title"))
        self.assertEqual(indexes["ix_task_series_is_active_starts_at"], ("is_active", "starts_at"))
        self.assertTrue(Task.__table__.columns.task_series_id.nullable)
        self.assertEqual(inspect(TaskSeries).relationships.tasks.back_populates, "task_series")
        self.assertEqual(inspect(Task).relationships.task_series.back_populates, "tasks")

    def test_foreign_keys_and_bidirectional_relationships(self) -> None:
        fks = {fk.parent.name: fk for fk in TaskSeries.__table__.foreign_keys}
        self.assertEqual((fks["workspace_id"].target_fullname, fks["workspace_id"].ondelete), ("workspaces.id", "CASCADE"))
        self.assertEqual((fks["created_by_id"].target_fullname, fks["created_by_id"].ondelete), ("users.id", "RESTRICT"))
        self.assertEqual((fks["category_id"].target_fullname, fks["category_id"].ondelete), ("categories.id", "SET NULL"))
        self.assertEqual((fks["project_id"].target_fullname, fks["project_id"].ondelete), ("projects.id", "SET NULL"))
        for owner, name, inverse in ((Workspace, "workspace", "task_series"), (User, "created_by", "created_task_series"), (Category, "category", "task_series"), (Project, "project", "task_series")):
            self.assertEqual(inspect(TaskSeries).relationships[name].back_populates, inverse)
            self.assertIsNotNone(inspect(owner).relationships[inverse])


if __name__ == "__main__": unittest.main()
