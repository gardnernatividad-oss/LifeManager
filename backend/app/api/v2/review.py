from fastapi import APIRouter

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.core.dates import local_today
from app.schemas.v2_review import GlobalReviewRead, ReviewPendingItem, ReviewProjectStageItem, ReviewTaskItem
from app.services.v2_review import get_global_review


router = APIRouter(prefix="/review", tags=["V2 Review"])


@router.get("", response_model=GlobalReviewRead)
def read_review(db: SessionDependency, account: UsableAccount) -> GlobalReviewRead:
    review_date = local_today(account.timezone)
    selection = get_global_review(db, user_id=account.id, local_date=review_date)
    return GlobalReviewRead(
        review_date=review_date,
        tasks=[ReviewTaskItem(
            id=task.id, workspace_id=workspace.id, workspace_name=workspace.name,
            planned_date=task.planned_date, lock_version=task.lock_version, task_name=master.name,
        ) for task, master, workspace in selection.tasks],
        pending_items=[ReviewPendingItem(
            id=item.id, workspace_id=workspace.id, workspace_name=workspace.name,
            planned_date=item.planned_date, lock_version=item.lock_version,
            pending_item_name=item.name, progress=item.progress,
        ) for item, workspace in selection.pending_items],
        project_stages=[ReviewProjectStageItem(
            id=stage.id, workspace_id=workspace.id, workspace_name=workspace.name,
            planned_date=stage.planned_date, lock_version=stage.lock_version,
            project_id=project.id, project_name=project.name, stage_name=stage.name,
            progress=stage.progress,
        ) for stage, project, workspace in selection.project_stages],
    )
