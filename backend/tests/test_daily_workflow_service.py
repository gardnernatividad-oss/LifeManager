import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import DailyFormDefinition, DailyFormSubmission, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.schemas.daily_workflow import DailyWorkflowStatus
from app.services.daily_workflow_service import initialize_daily_workflow
from app.services.task_series_service import TaskSeriesPermissionError


class DailyWorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.day = date(2026, 7, 22); self.now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)

    def generation(self, *, created: int = 0, skipped: int = 0) -> DailyTaskGenerationResponse:
        return DailyTaskGenerationResponse(
            workspace_id=self.workspace_id, generation_date=self.day,
            eligible_series_count=created + skipped, created_task_count=created,
            skipped_existing_count=skipped, created_task_ids=[uuid.uuid4() for _ in range(created)],
            generated_at=self.now,
        )

    def member(self, value: object = ...):
        return patch("app.services.daily_workflow_service.get_workspace_membership", return_value=self.membership if value is ... else value)

    def evaluate(self, scalar_values: list[object], generation: DailyTaskGenerationResponse | None = None):
        self.db.scalar.side_effect = scalar_values
        generated = generation or self.generation()
        with self.member() as membership, patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized",
            return_value=generated,
        ) as generator, patch("app.services.daily_workflow_service._utc_now", return_value=self.now):
            result = initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        membership.assert_called_once_with(self.db, workspace_id=self.workspace_id, user_id=self.user.id)
        generator.assert_called_once_with(self.db, workspace_id=self.workspace_id, generation_date=self.day)
        return result

    def test_no_definition_is_ready_and_embeds_zero_generation(self) -> None:
        result = self.evaluate([None])
        self.assertIs(result.workflow_status, DailyWorkflowStatus.READY)
        self.assertFalse(result.form_required); self.assertFalse(result.form_submitted)
        self.assertIsNone(result.definition_id); self.assertIsNone(result.submission_id)
        self.assertEqual(result.task_generation.created_task_count, 0)
        self.assertEqual(result.evaluated_at.utcoffset(), timezone.utc.utcoffset(result.evaluated_at))
        self.assertEqual(result.task_generation.generated_at.utcoffset(), timezone.utc.utcoffset(result.task_generation.generated_at))

    def test_definition_without_submission_requires_action(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        result = self.evaluate([definition, None], self.generation(created=1))
        self.assertIs(result.workflow_status, DailyWorkflowStatus.ACTION_REQUIRED)
        self.assertTrue(result.form_required); self.assertFalse(result.form_submitted)
        self.assertEqual(result.definition_id, definition.id); self.assertIsNone(result.submission_id)
        self.assertEqual(result.task_generation.created_task_count, 1)

    def test_current_definition_submission_is_ready_and_lookup_is_fully_scoped(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        submission = DailyFormSubmission(id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, definition_id=definition.id, submission_date=self.day)
        result = self.evaluate([definition, submission], self.generation(skipped=1))
        self.assertIs(result.workflow_status, DailyWorkflowStatus.READY)
        self.assertTrue(result.form_submitted); self.assertEqual(result.submission_id, submission.id)
        statement = self.db.scalar.call_args.args[0]; params = tuple(statement.compile().params.values())
        for value in (self.workspace_id, self.user.id, self.day, definition.id): self.assertIn(value, params)

    def test_other_date_user_workspace_or_old_definition_does_not_satisfy_current_query(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        for irrelevant in (
            DailyFormSubmission(workspace_id=self.workspace_id, user_id=self.user.id, definition_id=definition.id, submission_date=date(2026, 7, 21)),
            DailyFormSubmission(workspace_id=self.workspace_id, user_id=uuid.uuid4(), definition_id=definition.id, submission_date=self.day),
            DailyFormSubmission(workspace_id=uuid.uuid4(), user_id=self.user.id, definition_id=definition.id, submission_date=self.day),
            DailyFormSubmission(workspace_id=self.workspace_id, user_id=self.user.id, definition_id=uuid.uuid4(), submission_date=self.day),
        ):
            with self.subTest(irrelevant=irrelevant):
                self.db.reset_mock()
                result = self.evaluate([definition, None])
                self.assertIs(result.workflow_status, DailyWorkflowStatus.ACTION_REQUIRED)
                self.assertFalse(result.form_submitted)

    def test_repeated_calls_are_stable_and_service_never_owns_transaction(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        submission = DailyFormSubmission(id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, definition_id=definition.id, submission_date=self.day)
        first = self.evaluate([definition, submission], self.generation(created=1))
        self.db.reset_mock()
        repeated = self.evaluate([definition, submission], self.generation(skipped=1))
        self.assertEqual(first.workflow_status, repeated.workflow_status); self.assertEqual(first.submission_id, repeated.submission_id)
        self.assertEqual(repeated.task_generation.skipped_existing_count, 1)
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_nonmember_is_rejected_before_generation_or_queries(self) -> None:
        with self.member(None) as membership, patch(
            "app.services.daily_workflow_service.daily_task_generation_service.generate_daily_tasks_authorized",
        ) as generator, self.assertRaises(TaskSeriesPermissionError):
            initialize_daily_workflow(self.db, workspace_id=self.workspace_id, workflow_date=self.day, current_user=self.user)
        membership.assert_called_once(); generator.assert_not_called(); self.db.scalar.assert_not_called()
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
