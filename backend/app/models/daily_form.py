import enum
import uuid

from typing import TYPE_CHECKING

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Workspace


class DailyFormAnswerType(str, enum.Enum):
    BOOLEAN = "boolean"
    TEXT = "text"
    NUMBER = "number"


class DailyFormDefinition(BaseEntity):
    __tablename__ = "daily_form_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_daily_form_definitions_workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="daily_form_definition",
    )
    questions: Mapped[list["DailyFormQuestion"]] = relationship(
        "DailyFormQuestion",
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="DailyFormQuestion.order",
    )
    submissions: Mapped[list["DailyFormSubmission"]] = relationship(
        "DailyFormSubmission", back_populates="definition",
    )


class DailyFormQuestion(BaseEntity):
    __tablename__ = "daily_form_questions"
    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "order",
            name="uq_daily_form_questions_definition_id_order",
        ),
        CheckConstraint('"order" >= 1', name="ck_daily_form_questions_order_positive"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_daily_form_questions_title_not_blank"),
    )

    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("daily_form_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_type: Mapped[DailyFormAnswerType] = mapped_column(
        Enum(
            DailyFormAnswerType,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            name="dailyformanswertype",
        ),
        nullable=False,
    )

    definition: Mapped[DailyFormDefinition] = relationship(
        "DailyFormDefinition",
        back_populates="questions",
    )


class DailyFormSubmission(BaseEntity):
    __tablename__ = "daily_form_submissions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", "submission_date",
            name="uq_daily_form_submissions_workspace_user_date",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_form_definitions.id", ondelete="RESTRICT"), nullable=False,
    )
    submission_date: Mapped[date] = mapped_column(Date, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="daily_form_submissions")
    user: Mapped["User"] = relationship("User", back_populates="daily_form_submissions")
    definition: Mapped[DailyFormDefinition] = relationship("DailyFormDefinition", back_populates="submissions")
    answers: Mapped[list["DailyFormAnswer"]] = relationship(
        "DailyFormAnswer", back_populates="submission", cascade="all, delete-orphan",
        order_by="DailyFormAnswer.question_order",
    )


class DailyFormAnswer(BaseEntity):
    __tablename__ = "daily_form_answers"
    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_daily_form_answers_submission_question"),
        CheckConstraint(
            "(answer_type = 'boolean' AND boolean_value IS NOT NULL AND text_value IS NULL AND number_value IS NULL) OR "
            "(answer_type = 'text' AND boolean_value IS NULL AND text_value IS NOT NULL AND number_value IS NULL) OR "
            "(answer_type = 'number' AND boolean_value IS NULL AND text_value IS NULL AND number_value IS NOT NULL)",
            name="ck_daily_form_answers_value_matches_type",
        ),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_form_submissions.id", ondelete="CASCADE"), nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_title: Mapped[str] = mapped_column(String(255), nullable=False)
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_type: Mapped[DailyFormAnswerType] = mapped_column(
        Enum(DailyFormAnswerType, values_callable=lambda enum_type: [item.value for item in enum_type], name="dailyformanswertype"),
        nullable=False,
    )
    boolean_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    number_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    submission: Mapped[DailyFormSubmission] = relationship("DailyFormSubmission", back_populates="answers")
