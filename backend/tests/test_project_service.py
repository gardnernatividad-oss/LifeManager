import unittest
import uuid

from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Project, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import (
    ProjectNameConflictError, ProjectNotFoundError, ProjectPermissionError,
    activate_project, create_project, deactivate_project, get_project,
    list_projects, normalize_project_name, update_project,
)


class ProjectServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)

    def member(self, value: object = ...):
        result = self.membership if value is ... else value
        return patch("app.services.project_service.get_workspace_membership", return_value=result)

    def project(self, **changes: object) -> Project:
        values = dict(id=uuid.uuid4(), workspace_id=self.workspace_id, name="Personal", normalized_name="personal", description=None, is_active=True)
        values.update(changes)
        return Project(**values)

    def test_normalization_policy(self) -> None:
        self.assertEqual(normalize_project_name("  Proyecto   Personal "), ("Proyecto Personal", "proyecto personal"))
        self.assertEqual(normalize_project_name("TECNOLOGÍA")[1], normalize_project_name("Tecnología")[1])
        self.assertEqual(normalize_project_name("Tecnologi\u0301a"), ("Tecnología", "tecnología"))
        self.assertNotEqual(normalize_project_name("Tecnología")[1], normalize_project_name("Tecnologia")[1])
        with self.assertRaises(ValueError):
            normalize_project_name("ß" * 100)

    def test_create_cleans_scopes_and_never_commits(self) -> None:
        self.db.scalar.return_value = None
        with self.member():
            project = create_project(self.db, workspace_id=self.workspace_id, current_user=self.user, project_in=ProjectCreate(name="  Proyecto   Personal "))
        self.assertEqual((project.name, project.normalized_name), ("Proyecto Personal", "proyecto personal"))
        self.assertTrue(project.is_active)
        self.db.add.assert_called_once_with(project)
        self.db.flush.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_duplicate_variants_and_nonmember_are_rejected(self) -> None:
        for name in ("Personal", "PERSONAL", " Personal  "):
            self.db.reset_mock(); self.db.scalar.return_value = uuid.uuid4()
            with self.subTest(name=name), self.member(), self.assertRaises(ProjectNameConflictError):
                create_project(self.db, workspace_id=self.workspace_id, current_user=self.user, project_in=ProjectCreate(name=name))
        with self.member(None), self.assertRaises(ProjectPermissionError):
            list_projects(self.db, workspace_id=self.workspace_id, current_user=self.user)

    def test_integrity_race_is_selectively_translated(self) -> None:
        self.db.scalar.return_value = None
        original = MagicMock(); original.diag.constraint_name = "uq_projects_workspace_id_normalized_name"
        self.db.flush.side_effect = IntegrityError("duplicate", {}, original)
        with self.member(), self.assertRaises(ProjectNameConflictError):
            create_project(self.db, workspace_id=self.workspace_id, current_user=self.user, project_in=ProjectCreate(name="Personal"))
        self.db.flush.side_effect = IntegrityError("other", {}, Exception())
        with self.member(), self.assertRaises(IntegrityError):
            create_project(self.db, workspace_id=self.workspace_id, current_user=self.user, project_in=ProjectCreate(name="Other"))

    def test_list_filters_orders_and_get_is_scoped(self) -> None:
        expected = [self.project(is_active=False)]
        self.db.scalars.return_value.all.return_value = expected
        for active in (None, True, False):
            with self.subTest(active=active), self.member():
                self.assertEqual(list_projects(self.db, workspace_id=self.workspace_id, current_user=self.user, active=active), expected)
            sql = str(self.db.scalars.call_args.args[0])
            self.assertIn("ORDER BY projects.normalized_name, projects.name, projects.id", sql)
        self.db.scalar.return_value = expected[0]
        with self.member():
            self.assertIs(get_project(self.db, workspace_id=self.workspace_id, project_id=expected[0].id, current_user=self.user), expected[0])
        self.db.scalar.return_value = None
        with self.member(), self.assertRaises(ProjectNotFoundError):
            get_project(self.db, workspace_id=self.workspace_id, project_id=uuid.uuid4(), current_user=self.user)

    def test_update_clear_equivalent_name_and_activation_are_idempotent(self) -> None:
        project = self.project(); self.db.scalar.return_value = project
        with self.member():
            update_project(self.db, workspace_id=self.workspace_id, project_id=project.id, current_user=self.user, project_in=ProjectUpdate(name=" PERSONAL ", description=None))
        self.assertEqual(project.name, "PERSONAL"); self.assertIsNone(project.description)
        self.db.reset_mock(); self.db.scalar.return_value = project
        with self.member():
            deactivate_project(self.db, workspace_id=self.workspace_id, project_id=project.id, current_user=self.user)
        self.assertFalse(project.is_active); self.db.flush.assert_called_once()
        self.db.reset_mock(); self.db.scalar.return_value = project
        with self.member():
            deactivate_project(self.db, workspace_id=self.workspace_id, project_id=project.id, current_user=self.user)
        self.db.flush.assert_not_called()
        with self.member():
            activate_project(self.db, workspace_id=self.workspace_id, project_id=project.id, current_user=self.user)
        self.assertTrue(project.is_active)


if __name__ == "__main__":
    unittest.main()
