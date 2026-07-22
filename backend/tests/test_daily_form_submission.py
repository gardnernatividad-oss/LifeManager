import unittest
import uuid

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Session

from app.models import (
    DailyFormAnswer, DailyFormAnswerType, DailyFormDefinition, DailyFormQuestion,
    DailyFormSubmission, User, WorkspaceMember,
)
from app.models.workspace_member import WorkspaceRole
from app.schemas.daily_form_submission import DailyFormSubmissionRead, DailyFormSubmissionReplace
from app.services.daily_form_submission_service import (
    DailyFormDefinitionRequiredError, DailyFormSubmissionNotFoundError,
    DailyFormSubmissionPermissionError, DailyFormSubmissionValidationError,
    get_daily_form_submission, replace_daily_form_submission,
)


class DailyFormSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.day = date(2026, 7, 22); self.now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)
        self.questions = [
            DailyFormQuestion(id=uuid.uuid4(), order=2, title="Notes", answer_type=DailyFormAnswerType.TEXT),
            DailyFormQuestion(id=uuid.uuid4(), order=1, title="Ready", answer_type=DailyFormAnswerType.BOOLEAN),
            DailyFormQuestion(id=uuid.uuid4(), order=3, title="Score", answer_type=DailyFormAnswerType.NUMBER),
        ]
        self.definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id, questions=self.questions)

    def member(self, value: object = ...):
        return patch("app.services.daily_form_submission_service.get_workspace_membership", return_value=self.membership if value is ... else value)

    def payload(self, values: list[object] | None = None) -> DailyFormSubmissionReplace:
        values = values or ["notes", True, 4.5]
        return DailyFormSubmissionReplace.model_validate({"answers": [
            {"question_id": question.id, "value": value} for question, value in zip(self.questions, values)
        ]})

    def test_model_constraints_and_historical_snapshot_strategy(self) -> None:
        submission = DailyFormSubmission.__table__; answer = DailyFormAnswer.__table__
        self.assertIn("uq_daily_form_submissions_workspace_user_date", {item.name for item in submission.constraints if isinstance(item, UniqueConstraint)})
        self.assertIn("uq_daily_form_answers_submission_question", {item.name for item in answer.constraints if isinstance(item, UniqueConstraint)})
        self.assertIn("ck_daily_form_answers_value_matches_type", {item.name for item in answer.constraints if isinstance(item, CheckConstraint)})
        self.assertEqual(next(iter(submission.c.workspace_id.foreign_keys)).ondelete, "CASCADE")
        self.assertEqual(next(iter(submission.c.user_id.foreign_keys)).ondelete, "CASCADE")
        self.assertEqual(next(iter(submission.c.definition_id.foreign_keys)).ondelete, "RESTRICT")
        self.assertEqual(next(iter(answer.c.submission_id.foreign_keys)).ondelete, "CASCADE")
        self.assertFalse(answer.c.question_id.foreign_keys)

    def test_schema_rejects_duplicate_null_and_non_typed_values(self) -> None:
        question_id = uuid.uuid4()
        for answers in (
            [{"question_id": question_id, "value": True}, {"question_id": question_id, "value": False}],
            [{"question_id": question_id, "value": None}],
            [{"question_id": question_id, "value": {"bad": "value"}}],
        ):
            with self.assertRaises(ValidationError):
                DailyFormSubmissionReplace.model_validate({"answers": answers})

    def test_first_submission_flushes_without_owning_transaction_and_orders_snapshots(self) -> None:
        self.db.scalar.side_effect = [self.definition, None]
        with self.member():
            submission = replace_daily_form_submission(
                self.db, workspace_id=self.workspace_id, submission_date=self.day,
                current_user=self.user, submission_in=self.payload(),
            )
        self.assertEqual((submission.workspace_id, submission.user_id, submission.definition_id), (self.workspace_id, self.user.id, self.definition.id))
        self.assertEqual([answer.question_order for answer in submission.answers], [1, 2, 3])
        self.assertEqual(submission.answers[0].question_title, "Ready")
        self.db.add.assert_called_once_with(submission); self.assertEqual(self.db.flush.call_count, 2)
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_complete_replacement_preserves_submission_id(self) -> None:
        submission = DailyFormSubmission(id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, definition_id=uuid.uuid4(), submission_date=self.day, answers=[])
        original_id = submission.id; self.db.scalar.side_effect = [self.definition, submission]
        with self.member():
            result = replace_daily_form_submission(self.db, workspace_id=self.workspace_id, submission_date=self.day, current_user=self.user, submission_in=self.payload())
        self.assertEqual(result.id, original_id); self.assertEqual(result.definition_id, self.definition.id)
        self.db.add.assert_not_called(); self.db.flush.assert_called_once(); self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_validation_rejects_missing_extra_unknown_and_wrong_types(self) -> None:
        cases = [
            DailyFormSubmissionReplace(answers=[]),
            DailyFormSubmissionReplace.model_validate({"answers": [{"question_id": q.id, "value": v} for q, v in zip(self.questions[:2], ["x", True])]}),
            DailyFormSubmissionReplace.model_validate({"answers": [{"question_id": uuid.uuid4(), "value": "x"}, *self.payload().model_dump()["answers"]]}),
            self.payload(["x", 1, 4.5]),
            self.payload([False, True, 4.5]),
            self.payload(["x", True, False]),
            self.payload(["x", True, "4"]),
        ]
        for payload in cases:
            self.db.reset_mock(); self.db.scalar.return_value = self.definition
            with self.subTest(payload=payload.model_dump()), self.member(), self.assertRaises(DailyFormSubmissionValidationError):
                replace_daily_form_submission(self.db, workspace_id=self.workspace_id, submission_date=self.day, current_user=self.user, submission_in=payload)
            self.db.rollback.assert_not_called(); self.db.commit.assert_not_called()

    def test_missing_definition_authorization_and_scoped_retrieval(self) -> None:
        self.db.scalar.return_value = None
        with self.member(), self.assertRaises(DailyFormDefinitionRequiredError):
            replace_daily_form_submission(self.db, workspace_id=self.workspace_id, submission_date=self.day, current_user=self.user, submission_in=self.payload())
        self.db.reset_mock(); self.db.scalar.return_value = None
        with self.member(), self.assertRaises(DailyFormSubmissionNotFoundError):
            get_daily_form_submission(self.db, workspace_id=self.workspace_id, submission_date=self.day, current_user=self.user)
        params = tuple(self.db.scalar.call_args.args[0].compile().params.values())
        self.assertIn(self.workspace_id, params); self.assertIn(self.user.id, params); self.assertIn(self.day, params)
        with self.member(None), self.assertRaises(DailyFormSubmissionPermissionError):
            get_daily_form_submission(self.db, workspace_id=uuid.uuid4(), submission_date=self.day, current_user=self.user)

    def test_historical_response_does_not_depend_on_current_question(self) -> None:
        answer = DailyFormAnswer(question_id=self.questions[0].id, question_title="Original", question_order=1, answer_type=DailyFormAnswerType.TEXT, text_value="saved")
        submission = DailyFormSubmission(id=uuid.uuid4(), workspace_id=self.workspace_id, user_id=self.user.id, definition_id=self.definition.id, submission_date=self.day, answers=[answer], created_at=self.now, updated_at=self.now)
        self.questions[0].title = "Replacement"
        response = DailyFormSubmissionRead.from_submission(submission)
        self.assertEqual(response.answers[0].question_title, "Original"); self.assertEqual(response.answers[0].value, "saved")


if __name__ == "__main__":
    unittest.main()
