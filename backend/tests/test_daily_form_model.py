import unittest

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models import DailyFormAnswerType, DailyFormDefinition, DailyFormQuestion, Workspace
from app.models.base import Base


class DailyFormModelTests(unittest.TestCase):
    def test_definition_and_questions_metadata(self) -> None:
        definition = DailyFormDefinition.__table__
        question = DailyFormQuestion.__table__
        self.assertIs(Base.metadata.tables["daily_form_definitions"], definition)
        self.assertIs(Base.metadata.tables["daily_form_questions"], question)
        self.assertFalse(definition.c.workspace_id.nullable)
        self.assertIn("uq_daily_form_definitions_workspace_id", {item.name for item in definition.constraints if isinstance(item, UniqueConstraint)})
        workspace_fk = next(iter(definition.c.workspace_id.foreign_keys))
        self.assertEqual(workspace_fk.target_fullname, "workspaces.id"); self.assertEqual(workspace_fk.ondelete, "CASCADE")
        self.assertEqual(question.c.title.type.length, 255); self.assertTrue(question.c.description.nullable)
        self.assertIn("uq_daily_form_questions_definition_id_order", {item.name for item in question.constraints if isinstance(item, UniqueConstraint)})
        checks = {item.name for item in question.constraints if isinstance(item, CheckConstraint)}
        self.assertIn("ck_daily_form_questions_order_positive", checks); self.assertIn("ck_daily_form_questions_title_not_blank", checks)
        question_fk = next(iter(question.c.definition_id.foreign_keys))
        self.assertEqual(question_fk.ondelete, "CASCADE")
        self.assertEqual(DailyFormDefinition.questions.property.back_populates, "definition")
        self.assertEqual(DailyFormQuestion.definition.property.back_populates, "questions")
        self.assertEqual(Workspace.daily_form_definition.property.back_populates, "workspace")
        self.assertEqual([item.value for item in DailyFormAnswerType], ["boolean", "text", "number"])


if __name__ == "__main__":
    unittest.main()
