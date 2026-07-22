import enum
import uuid

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
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
