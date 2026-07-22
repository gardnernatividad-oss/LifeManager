import uuid

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator

from app.models.daily_form import DailyFormAnswerType, DailyFormSubmission


AnswerValue = StrictBool | StrictStr | StrictInt | StrictFloat


class DailyFormAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: uuid.UUID
    value: AnswerValue


class DailyFormSubmissionReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[DailyFormAnswerSubmit]

    @field_validator("answers")
    @classmethod
    def question_ids_must_be_unique(cls, answers: list[DailyFormAnswerSubmit]) -> list[DailyFormAnswerSubmit]:
        question_ids = [answer.question_id for answer in answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Duplicate question IDs are not allowed")
        return answers


class DailyFormAnswerRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: uuid.UUID
    question_title: str
    question_order: int
    answer_type: DailyFormAnswerType
    value: bool | str | float


class DailyFormSubmissionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    definition_id: uuid.UUID
    submission_date: date
    answers: list[DailyFormAnswerRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_submission(cls, submission: DailyFormSubmission) -> "DailyFormSubmissionRead":
        answers = []
        for answer in sorted(submission.answers, key=lambda item: item.question_order):
            value = {
                DailyFormAnswerType.BOOLEAN: answer.boolean_value,
                DailyFormAnswerType.TEXT: answer.text_value,
                DailyFormAnswerType.NUMBER: answer.number_value,
            }[answer.answer_type]
            answers.append(DailyFormAnswerRead(
                question_id=answer.question_id, question_title=answer.question_title,
                question_order=answer.question_order, answer_type=answer.answer_type, value=value,
            ))
        return cls(
            id=submission.id, workspace_id=submission.workspace_id, user_id=submission.user_id,
            definition_id=submission.definition_id, submission_date=submission.submission_date,
            answers=answers, created_at=submission.created_at, updated_at=submission.updated_at,
        )
