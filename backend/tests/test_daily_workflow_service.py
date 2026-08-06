import unittest
import uuid

from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import DailyFormDefinition, DailyFormSubmission, User, WeekStartsOn, WorkspaceSettings
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.schemas.daily_workflow import DailyWorkflowStatus
from app.services.daily_form_service import DailyFormNotFoundError
from app.services.daily_form_submission_service import DailyFormSubmissionNotFoundError
from app.services.daily_workflow_service import initialize_daily_workflow
from app.services.task_series_service import TaskSeriesPermissionError
from app.services.workspace_settings_service import WorkspaceSettingsPermissionError


class DailyWorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.day = date(2026, 8, 6); self.now = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)

    def settings(self, *, generation: bool = True, form: bool = True) -> WorkspaceSettings:
        return WorkspaceSettings(
            id=uuid.uuid4(), workspace_id=self.workspace_id, timezone="America/Lima",
            daily_form_enabled=form, daily_form_reminder_time=time(9),
            daily_task_generation_enabled=generation, week_starts_on=WeekStartsOn.MONDAY,
        )

    def generation(self) -> DailyTaskGenerationResponse:
        return DailyTaskGenerationResponse(
            workspace_id=self.workspace_id, generation_date=self.day,
            eligible_series_count=1, created_task_count=1, skipped_existing_count=0,
            created_task_ids=[uuid.uuid4()], generated_at=self.now,
        )

    def test_generation_disabled_skips_service_and_returns_zero_summary(self) -> None:
        with patch("app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings", return_value=self.settings(generation=False)), patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized",
        ) as generation, patch(
            "app.services.daily_workflow_service.daily_form_service.get_daily_form_definition",
            side_effect=DailyFormNotFoundError("missing"),
        ), patch("app.services.daily_workflow_service._utc_now", return_value=self.now):
            result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        generation.assert_not_called()
        self.assertEqual(
            (result.task_generation.eligible_series_count, result.task_generation.created_task_count,
             result.task_generation.skipped_existing_count, result.task_generation.created_task_ids),
            (0, 0, 0, []),
        )

    def test_form_disabled_skips_form_services_and_is_ready(self) -> None:
        generated = self.generation()
        with patch("app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings", return_value=self.settings(form=False)), patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized", return_value=generated,
        ), patch("app.services.daily_workflow_service.daily_form_service.get_daily_form_definition") as definition, patch(
            "app.services.daily_workflow_service.daily_form_submission_service.get_daily_form_submission",
        ) as submission, patch("app.services.daily_workflow_service._utc_now", return_value=self.now):
            result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        definition.assert_not_called(); submission.assert_not_called()
        self.assertIs(result.workflow_status, DailyWorkflowStatus.READY)
        self.assertFalse(result.form_required); self.assertFalse(result.form_submitted)
        self.assertIsNone(result.definition_id); self.assertIsNone(result.submission_id)

    def test_both_disabled_skip_both_branches_and_remain_ready(self) -> None:
        with patch("app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings", return_value=self.settings(generation=False, form=False)) as settings, patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized",
        ) as generation, patch("app.services.daily_workflow_service.daily_form_service.get_daily_form_definition") as definition, patch(
            "app.services.daily_workflow_service._utc_now", return_value=self.now,
        ):
            result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        settings.assert_called_once_with(self.db, workspace_id=self.workspace_id, current_user=self.user)
        generation.assert_not_called(); definition.assert_not_called()
        self.assertIs(result.workflow_status, DailyWorkflowStatus.READY)

    def test_both_enabled_preserve_definition_submission_and_generation_behavior(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        submission = DailyFormSubmission(id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, definition_id=definition.id, submission_date=self.day)
        generated = self.generation()
        with patch("app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings", return_value=self.settings()), patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized", return_value=generated,
        ) as generation, patch(
            "app.services.daily_workflow_service.daily_form_service.get_daily_form_definition", return_value=definition,
        ) as form, patch(
            "app.services.daily_workflow_service.daily_form_submission_service.get_daily_form_submission", return_value=submission,
        ) as submitted, patch("app.services.daily_workflow_service._utc_now", return_value=self.now):
            result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        generation.assert_called_once_with(self.db, workspace_id=self.workspace_id, generation_date=self.day)
        form.assert_called_once_with(self.db, workspace_id=self.workspace_id, current_user=self.user)
        submitted.assert_called_once_with(self.db, workspace_id=self.workspace_id, submission_date=self.day, current_user=self.user)
        self.assertIs(result.workflow_status, DailyWorkflowStatus.READY); self.assertTrue(result.form_submitted)
        self.assertEqual(result.submission_id, submission.id); self.assertIs(result.task_generation, generated)

    def test_enabled_form_without_submission_requires_action_and_old_definition_does_not_satisfy(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        old = DailyFormSubmission(id=uuid.uuid4(), definition_id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, submission_date=self.day)
        for outcome in (DailyFormSubmissionNotFoundError("missing"), old):
            context = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
            with self.subTest(outcome=type(outcome).__name__), patch("app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings", return_value=self.settings()), patch(
                "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized", return_value=self.generation(),
            ), patch("app.services.daily_workflow_service.daily_form_service.get_daily_form_definition", return_value=definition), patch(
                "app.services.daily_workflow_service.daily_form_submission_service.get_daily_form_submission", **context,
            ), patch("app.services.daily_workflow_service._utc_now", return_value=self.now):
                result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
            self.assertIs(result.workflow_status, DailyWorkflowStatus.ACTION_REQUIRED); self.assertFalse(result.form_submitted)

    def test_authorization_and_transaction_ownership_remain_unchanged(self) -> None:
        with patch(
            "app.services.daily_workflow_service.workspace_settings_service.get_or_create_workspace_settings",
            side_effect=WorkspaceSettingsPermissionError("Workspace access denied"),
        ), patch("app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized") as generation, self.assertRaises(TaskSeriesPermissionError):
            initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        generation.assert_not_called(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__": unittest.main()
