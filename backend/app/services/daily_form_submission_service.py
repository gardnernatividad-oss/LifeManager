import uuid

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.daily_form import (
    DailyFormAnswer, DailyFormAnswerType, DailyFormDefinition, DailyFormSubmission,
)
from app.models.user import User
from app.schemas.daily_form_submission import DailyFormSubmissionReplace
from app.services.workspace import get_workspace_membership


class DailyFormSubmissionNotFoundError(LookupError):
    pass


class DailyFormSubmissionPermissionError(PermissionError):
    pass


class DailyFormDefinitionRequiredError(ValueError):
    pass


class DailyFormSubmissionValidationError(ValueError):
    pass


def _require_membership(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if get_workspace_membership(db, workspace_id=workspace_id, user_id=user_id) is None:
        raise DailyFormSubmissionPermissionError("Workspace access denied")


def _submission_statement(*, workspace_id: uuid.UUID, user_id: uuid.UUID, submission_date: date):
    return (
        select(DailyFormSubmission)
        .options(selectinload(DailyFormSubmission.answers))
        .where(
            DailyFormSubmission.workspace_id == workspace_id,
            DailyFormSubmission.user_id == user_id,
            DailyFormSubmission.submission_date == submission_date,
        )
    )


def get_daily_form_submission(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    submission_date: date,
    current_user: User,
) -> DailyFormSubmission:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    submission = db.scalar(_submission_statement(
        workspace_id=workspace_id, user_id=current_user.id, submission_date=submission_date,
    ))
    if submission is None:
        raise DailyFormSubmissionNotFoundError("Daily form submission not found")
    return submission


def _answer_for_question(question, value: object) -> DailyFormAnswer:
    if question.answer_type is DailyFormAnswerType.BOOLEAN and type(value) is not bool:
        raise DailyFormSubmissionValidationError(f"Question {question.id} requires a Boolean value")
    if question.answer_type is DailyFormAnswerType.TEXT and type(value) is not str:
        raise DailyFormSubmissionValidationError(f"Question {question.id} requires a text value")
    if question.answer_type is DailyFormAnswerType.NUMBER and type(value) not in (int, float):
        raise DailyFormSubmissionValidationError(f"Question {question.id} requires a number value")
    values = {"boolean_value": None, "text_value": None, "number_value": None}
    values[{DailyFormAnswerType.BOOLEAN: "boolean_value", DailyFormAnswerType.TEXT: "text_value", DailyFormAnswerType.NUMBER: "number_value"}[question.answer_type]] = value
    return DailyFormAnswer(
        question_id=question.id, question_title=question.title, question_order=question.order,
        answer_type=question.answer_type, **values,
    )


def replace_daily_form_submission(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    submission_date: date,
    current_user: User,
    submission_in: DailyFormSubmissionReplace,
) -> DailyFormSubmission:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    definition = db.scalar(
        select(DailyFormDefinition)
        .options(selectinload(DailyFormDefinition.questions))
        .where(DailyFormDefinition.workspace_id == workspace_id)
    )
    if definition is None:
        raise DailyFormDefinitionRequiredError("Daily form definition not found")

    questions = {question.id: question for question in definition.questions}
    submitted = {answer.question_id: answer.value for answer in submission_in.answers}
    missing = questions.keys() - submitted.keys()
    extra = submitted.keys() - questions.keys()
    if missing:
        raise DailyFormSubmissionValidationError("Answers are required for every active question")
    if extra:
        raise DailyFormSubmissionValidationError("Unknown question IDs are not allowed")

    answers = [_answer_for_question(question, submitted[question.id]) for question in sorted(questions.values(), key=lambda item: item.order)]
    submission = db.scalar(_submission_statement(
        workspace_id=workspace_id, user_id=current_user.id, submission_date=submission_date,
    ))
    if submission is None:
        submission = DailyFormSubmission(
            workspace_id=workspace_id, user_id=current_user.id,
            definition_id=definition.id, submission_date=submission_date,
        )
        db.add(submission)
        db.flush()
    else:
        submission.definition_id = definition.id
    submission.answers = answers
    db.flush()
    return submission
