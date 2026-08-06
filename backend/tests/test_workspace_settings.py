import unittest
import uuid

from datetime import time
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Session

from app.models import User, WeekStartsOn, Workspace, WorkspaceMember, WorkspaceSettings
from app.models.workspace_member import WorkspaceRole
from app.schemas.workspace_settings import WorkspaceSettingsReplace
from app.services.workspace_settings_service import (
    WorkspaceSettingsPermissionError, get_or_create_workspace_settings, replace_workspace_settings,
)


class WorkspaceSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.workspace = Workspace(id=self.workspace_id, name="Home", timezone="Europe/Madrid")

    def member(self, role: WorkspaceRole | None):
        value = None if role is None else WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=role)
        return patch("app.services.workspace_settings_service.get_workspace_membership", return_value=value)

    @staticmethod
    def payload(**changes: object) -> WorkspaceSettingsReplace:
        values = dict(timezone=" America/New_York ", daily_form_enabled=False,
                      daily_form_reminder_time="08:30:00", daily_task_generation_enabled=True,
                      week_starts_on="SUNDAY")
        values.update(changes); return WorkspaceSettingsReplace.model_validate(values)

    def test_model_constraints_defaults_cascade_and_one_to_one(self) -> None:
        table = WorkspaceSettings.__table__
        self.assertIn("uq_workspace_settings_workspace_id", {x.name for x in table.constraints if isinstance(x, UniqueConstraint)})
        self.assertIn("ck_workspace_settings_timezone_not_blank", {x.name for x in table.constraints if isinstance(x, CheckConstraint)})
        self.assertEqual(next(iter(table.c.workspace_id.foreign_keys)).ondelete, "CASCADE")
        self.assertFalse(Workspace.settings.property.uselist); self.assertIn("delete-orphan", Workspace.settings.property.cascade)
        self.assertTrue(Workspace.settings.property.single_parent)
        self.assertEqual(table.c.timezone.default.arg, "America/Lima")
        self.assertIs(table.c.daily_form_enabled.default.arg, True); self.assertIs(table.c.daily_task_generation_enabled.default.arg, True)

    def test_schema_timezone_enum_time_flags_and_protected_fields(self) -> None:
        schema = self.payload(); self.assertEqual(schema.timezone, "America/New_York")
        self.assertEqual(schema.daily_form_reminder_time, time(8, 30)); self.assertIs(schema.week_starts_on, WeekStartsOn.SUNDAY)
        for zone in ("America/Lima", "UTC", "Europe/Madrid"):
            self.assertEqual(self.payload(timezone=zone).timezone, zone)
        for changes in ({"timezone": " "}, {"timezone": "Bad/Zone"}, {"week_starts_on": "BAD"}, {"workspace_id": uuid.uuid4()}):
            values = self.payload().model_dump(mode="json"); values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError): WorkspaceSettingsReplace.model_validate(values)

    def test_first_get_copies_workspace_timezone_exact_defaults_and_repeated_get_reuses(self) -> None:
        self.db.scalar.side_effect = [self.workspace, None]
        with self.member(WorkspaceRole.MEMBER): settings = get_or_create_workspace_settings(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.assertEqual((settings.timezone, settings.daily_form_enabled, settings.daily_form_reminder_time, settings.daily_task_generation_enabled, settings.week_starts_on),
                         ("Europe/Madrid", True, time(9), True, WeekStartsOn.MONDAY))
        self.db.add.assert_called_once_with(settings); self.db.flush.assert_called_once(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()
        self.db.reset_mock(); self.db.scalar.side_effect = [self.workspace, settings]
        with self.member(WorkspaceRole.MEMBER): self.assertIs(get_or_create_workspace_settings(self.db, workspace_id=self.workspace_id, current_user=self.user), settings)
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()

    def test_owner_and_admin_replace_create_or_preserve_identity_and_workspace(self) -> None:
        for role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            for existing in (None, WorkspaceSettings(id=uuid.uuid4(), workspace_id=self.workspace_id)):
                self.db.reset_mock(); self.db.scalar.side_effect = [self.workspace, existing]
                original_id = existing.id if existing else None
                with self.subTest(role=role, existing=existing is not None), self.member(role):
                    result = replace_workspace_settings(self.db, workspace_id=self.workspace_id, current_user=self.user, settings_in=self.payload())
                if original_id: self.assertEqual(result.id, original_id)
                self.assertEqual(result.workspace_id, self.workspace_id); self.assertFalse(result.daily_form_enabled); self.assertTrue(result.daily_task_generation_enabled)
                self.db.flush.assert_called_once(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_member_and_nonmember_cannot_replace_and_nonmember_cannot_get(self) -> None:
        for role in (WorkspaceRole.MEMBER, WorkspaceRole.VIEWER, None):
            with self.subTest(role=role), self.member(role), self.assertRaises(WorkspaceSettingsPermissionError):
                replace_workspace_settings(self.db, workspace_id=self.workspace_id, current_user=self.user, settings_in=self.payload())
        with self.member(None), self.assertRaises(WorkspaceSettingsPermissionError):
            get_or_create_workspace_settings(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.db.add.assert_not_called(); self.db.flush.assert_not_called()


if __name__ == "__main__": unittest.main()
