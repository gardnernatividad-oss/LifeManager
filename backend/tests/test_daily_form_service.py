import unittest
import uuid

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models import DailyFormAnswerType, DailyFormDefinition, DailyFormQuestion, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas.daily_form import DailyFormDefinitionReplace
from app.services.daily_form_service import (
    DailyFormNotFoundError, DailyFormPermissionError,
    get_daily_form_definition, replace_daily_form_definition,
)


class DailyFormServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session); self.workspace_id = uuid.uuid4(); self.user = User(id=uuid.uuid4())
        self.membership = WorkspaceMember(workspace_id=self.workspace_id, user_id=self.user.id, role=WorkspaceRole.MEMBER)

    def member(self, value: object = ...):
        return patch("app.services.daily_form_service.get_workspace_membership", return_value=self.membership if value is ... else value)

    def test_empty_definition_is_not_found_and_workspace_query_is_scoped(self) -> None:
        self.db.scalar.return_value = None
        with self.member(), self.assertRaises(DailyFormNotFoundError):
            get_daily_form_definition(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.assertIn(self.workspace_id, self.db.scalar.call_args.args[0].compile().params.values())
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_replacement_creates_and_orders_complete_question_set_transactionally(self) -> None:
        self.db.scalar.return_value = None
        payload = DailyFormDefinitionReplace.model_validate({"questions": [
            {"order": 2, "title": "Second", "answer_type": "text"},
            {"order": 1, "title": "First", "answer_type": "boolean"},
        ]})
        with self.member():
            definition = replace_daily_form_definition(self.db, workspace_id=self.workspace_id, current_user=self.user, definition_in=payload)
        self.assertEqual(definition.workspace_id, self.workspace_id)
        self.assertEqual([item.order for item in definition.questions], [1, 2])
        self.assertEqual(definition.questions[0].answer_type, DailyFormAnswerType.BOOLEAN)
        self.db.add.assert_called_once_with(definition); self.assertEqual(self.db.flush.call_count, 2)
        self.db.commit.assert_not_called(); self.db.rollback.assert_not_called()

    def test_replacement_removes_old_questions_and_preserves_definition(self) -> None:
        definition = DailyFormDefinition(id=uuid.uuid4(), workspace_id=self.workspace_id)
        old = DailyFormQuestion(order=1, title="Old", answer_type=DailyFormAnswerType.TEXT)
        definition.questions = [old]; self.db.scalar.return_value = definition
        payload = DailyFormDefinitionReplace.model_validate({"questions": [{"order": 1, "title": "New", "answer_type": "number"}]})
        with self.member():
            result = replace_daily_form_definition(self.db, workspace_id=self.workspace_id, current_user=self.user, definition_in=payload)
        self.assertIs(result, definition); self.assertEqual([item.title for item in result.questions], ["New"])
        self.db.add.assert_not_called(); self.db.flush.assert_called_once(); self.db.commit.assert_not_called()

    def test_nonmember_is_denied_before_definition_lookup(self) -> None:
        with self.member(None), self.assertRaises(DailyFormPermissionError):
            get_daily_form_definition(self.db, workspace_id=self.workspace_id, current_user=self.user)
        self.db.scalar.assert_not_called(); self.db.flush.assert_not_called(); self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
