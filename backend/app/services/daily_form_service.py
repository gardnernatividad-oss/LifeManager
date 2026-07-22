import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.daily_form import DailyFormDefinition, DailyFormQuestion
from app.models.user import User
from app.schemas.daily_form import DailyFormDefinitionReplace
from app.services.workspace import get_workspace_membership


class DailyFormNotFoundError(LookupError):
    pass


class DailyFormPermissionError(PermissionError):
    pass


def _require_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership is None:
        raise DailyFormPermissionError("Workspace access denied")


def _definition_statement(workspace_id: uuid.UUID):
    return (
        select(DailyFormDefinition)
        .options(selectinload(DailyFormDefinition.questions))
        .where(DailyFormDefinition.workspace_id == workspace_id)
    )


def get_daily_form_definition(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
) -> DailyFormDefinition:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    definition = db.scalar(_definition_statement(workspace_id))
    if definition is None:
        raise DailyFormNotFoundError("Daily form definition not found")
    return definition


def replace_daily_form_definition(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    definition_in: DailyFormDefinitionReplace,
) -> DailyFormDefinition:
    _require_membership(db, workspace_id=workspace_id, user_id=current_user.id)
    definition = db.scalar(_definition_statement(workspace_id))
    if definition is None:
        definition = DailyFormDefinition(workspace_id=workspace_id)
        db.add(definition)
        db.flush()

    definition.questions = [
        DailyFormQuestion(**question.model_dump())
        for question in sorted(definition_in.questions, key=lambda item: item.order)
    ]
    db.flush()
    return definition
