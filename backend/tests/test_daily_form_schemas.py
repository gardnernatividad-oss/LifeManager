import unittest

from pydantic import ValidationError

from app.schemas.daily_form import DailyFormDefinitionReplace


class DailyFormSchemaTests(unittest.TestCase):
    def question(self, order: int = 1, **changes: object) -> dict[str, object]:
        values: dict[str, object] = {"order": order, "title": " Question ", "description": None, "answer_type": "boolean"}
        values.update(changes)
        return values

    def test_valid_definition_cleans_title_and_accepts_supported_types(self) -> None:
        schema = DailyFormDefinitionReplace(questions=[
            self.question(2, answer_type="text"), self.question(1, answer_type="number"),
        ])
        self.assertEqual(schema.questions[0].title, "Question")

    def test_empty_too_large_duplicate_order_and_invalid_questions_are_rejected(self) -> None:
        invalid = (
            {"questions": []},
            {"questions": [self.question(index + 1) for index in range(31)]},
            {"questions": [self.question(1), self.question(1)]},
            {"questions": [self.question(title="   ")]},
            {"questions": [self.question(answer_type="choice")]},
            {"questions": [self.question(order=0)]},
        )
        for payload in invalid:
            with self.subTest(payload=len(payload["questions"])), self.assertRaises(ValidationError):
                DailyFormDefinitionReplace.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
