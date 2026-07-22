import uuid

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_form import DailyFormDefinition, DailyFormSubmission
from app.models.user import User
from app.schemas.daily_workflow import DailyWorkflowResponse, DailyWorkflowStatus
from app.services import daily_task_generation_service
from app.services.task_series_service import TaskSeriesPermissionError
from app.services.workspace import get_workspace_membership


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_daily_workflow(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    workflow_date: date,
    current_user: User,
) -> DailyWorkflowResponse:
    if get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    ) is None:
        raise TaskSeriesPermissionError("Workspace access denied")

    task_generation = daily_task_generation_service.generate_daily_tasks_authorized(
        db,
        workspace_id=workspace_id,
        generation_date=workflow_date,
    )
    definition = db.scalar(
        select(DailyFormDefinition).where(
            DailyFormDefinition.workspace_id == workspace_id,
        )
    )
    submission = None
    if definition is not None:
        submission = db.scalar(
            select(DailyFormSubmission).where(
                DailyFormSubmission.workspace_id == workspace_id,
                DailyFormSubmission.user_id == current_user.id,
                DailyFormSubmission.submission_date == workflow_date,
                DailyFormSubmission.definition_id == definition.id,
            )
        )

    form_required = definition is not None
    form_submitted = submission is not None
    return DailyWorkflowResponse(
        workspace_id=workspace_id,
        user_id=current_user.id,
        workflow_date=workflow_date,
        workflow_status=(
            DailyWorkflowStatus.READY
            if not form_required or form_submitted
            else DailyWorkflowStatus.ACTION_REQUIRED
        ),
        form_required=form_required,
        form_submitted=form_submitted,
        definition_id=definition.id if definition is not None else None,
        submission_id=submission.id if submission is not None else None,
        task_generation=task_generation,
        evaluated_at=_utc_now(),
    )
