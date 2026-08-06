import uuid

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.daily_task_generation import DailyTaskGenerationResponse
from app.schemas.daily_workflow import DailyWorkflowResponse, DailyWorkflowStatus
from app.services import (
    daily_form_service,
    daily_form_submission_service,
    daily_task_generation_service,
    workspace_settings_service,
)
from app.services.task_series_service import TaskSeriesPermissionError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_daily_workflow(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    workflow_date: date,
    current_user: User,
) -> DailyWorkflowResponse:
    evaluated_at = _utc_now()
    try:
        settings = workspace_settings_service.get_or_create_workspace_settings(
            db,
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except workspace_settings_service.WorkspaceSettingsPermissionError as error:
        raise TaskSeriesPermissionError(str(error)) from error

    if settings.daily_task_generation_enabled:
        task_generation = daily_task_generation_service.generate_daily_tasks_authorized(
            db,
            workspace_id=workspace_id,
            generation_date=workflow_date,
        )
    else:
        task_generation = DailyTaskGenerationResponse(
            workspace_id=workspace_id,
            generation_date=workflow_date,
            eligible_series_count=0,
            created_task_count=0,
            skipped_existing_count=0,
            created_task_ids=[],
            generated_at=evaluated_at,
        )

    definition = None
    submission = None
    if settings.daily_form_enabled:
        try:
            definition = daily_form_service.get_daily_form_definition(
                db,
                workspace_id=workspace_id,
                current_user=current_user,
            )
        except daily_form_service.DailyFormNotFoundError:
            definition = None
        if definition is not None:
            try:
                candidate = daily_form_submission_service.get_daily_form_submission(
                    db,
                    workspace_id=workspace_id,
                    submission_date=workflow_date,
                    current_user=current_user,
                )
            except daily_form_submission_service.DailyFormSubmissionNotFoundError:
                candidate = None
            if candidate is not None and candidate.definition_id == definition.id:
                submission = candidate

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
        evaluated_at=evaluated_at,
    )
