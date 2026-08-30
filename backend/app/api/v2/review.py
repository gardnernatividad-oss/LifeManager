from fastapi import APIRouter

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.schemas.v2_review import GlobalReviewRead, ReviewBlockSaveResponse, ReviewPendingItem, ReviewPendingItemBatch, ReviewProjectStageBatch, ReviewProjectStageItem, ReviewTaskBatch, ReviewTaskItem
from app.services.v2_review import ReviewConflictError, ReviewNotFoundError, get_global_review, save_review_pending_items, save_review_project_stages, save_review_tasks


router = APIRouter(prefix="/review", tags=["V2 Review"])


@router.get("", response_model=GlobalReviewRead)
def read_review(db: SessionDependency, account: UsableAccount) -> GlobalReviewRead:
    review_date = local_today(account.timezone)
    selection = get_global_review(db, user_id=account.id, local_date=review_date)
    return GlobalReviewRead(
        review_date=review_date,
        tasks=[ReviewTaskItem(
            id=task.id, workspace_id=workspace.id, workspace_name=workspace.name,
            planned_date=task.planned_date, lock_version=task.lock_version,
            task_name=master.name if master is not None else task.custom_name,
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
            progress=stage.progress, project_lock_version=project.lock_version,
        ) for stage, project, workspace in selection.project_stages],
    )


def _save_block(db: SessionDependency, operation) -> ReviewBlockSaveResponse:
    try:
        saved = operation()
        db.commit()
        return ReviewBlockSaveResponse(saved_ids=[item.id for item in saved])
    except ReviewNotFoundError as error:
        db.rollback()
        raise V2APIError(
            status_code=404,
            code="REVIEW_ITEM_NOT_FOUND",
            message="No se encontró un elemento disponible para Revisión.",
        ) from error
    except ReviewConflictError as error:
        db.rollback()
        raise V2APIError(
            status_code=409,
            code="REVIEW_CONFLICT",
            message="La información de Revisión cambió. Actualiza el bloque e inténtalo nuevamente.",
        ) from error
    except Exception:
        db.rollback()
        raise


@router.post("/tasks", response_model=ReviewBlockSaveResponse)
def save_tasks(
    batch: ReviewTaskBatch,
    db: SessionDependency,
    account: UsableAccount,
) -> ReviewBlockSaveResponse:
    return _save_block(db, lambda: save_review_tasks(
        db, actor=account, changes=batch.items, local_date=local_today(account.timezone)
    ))


@router.post("/pending-items", response_model=ReviewBlockSaveResponse)
def save_pending_items(
    batch: ReviewPendingItemBatch,
    db: SessionDependency,
    account: UsableAccount,
) -> ReviewBlockSaveResponse:
    return _save_block(db, lambda: save_review_pending_items(
        db, actor=account, changes=batch.items, local_date=local_today(account.timezone)
    ))


@router.post("/project-stages", response_model=ReviewBlockSaveResponse)
def save_project_stages(
    batch: ReviewProjectStageBatch,
    db: SessionDependency,
    account: UsableAccount,
) -> ReviewBlockSaveResponse:
    return _save_block(db, lambda: save_review_project_stages(
        db, actor=account, changes=batch.items, local_date=local_today(account.timezone)
    ))
