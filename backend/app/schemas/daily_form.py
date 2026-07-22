import uuid

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.daily_form import DailyFormAnswerType


QuestionTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class DailyFormQuestionReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1)
    title: QuestionTitle
    description: str | None = None
    answer_type: DailyFormAnswerType


class DailyFormDefinitionReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[DailyFormQuestionReplace] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def question_orders_must_be_unique(self) -> "DailyFormDefinitionReplace":
        orders = [question.order for question in self.questions]
        if len(orders) != len(set(orders)):
            raise ValueError("Question order values must be unique")
        return self


class DailyFormQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    order: int
    title: str
    description: str | None
    answer_type: DailyFormAnswerType


class DailyFormDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    workspace_id: uuid.UUID
    questions: list[DailyFormQuestionRead]
    created_at: datetime
    updated_at: datetime
