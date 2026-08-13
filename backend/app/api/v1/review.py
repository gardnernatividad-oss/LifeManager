from collections import OrderedDict

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.review import (
    ReviewPendingItemRead,
    ReviewProjectGroupRead,
    ReviewProjectStepRead,
    ReviewRead,
    ReviewSave,
    ReviewSaveResponse,
    ReviewTaskRead,
)
from app.services import review_service


router = APIRouter(prefix="/review", tags=["Review"])

_DOMAIN_ERRORS = (
    review_service.ReviewNotFoundError,
    review_service.ReviewConflictError,
    review_service.ReviewVersionConflictError,
)


def _error(error: Exception) -> HTTPException:
    if isinstance(error, review_service.ReviewNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


@router.get("", response_model=ReviewRead)
def get_review(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ReviewRead:
    review_date = local_today(current_user.timezone)
    tasks, pending_items, steps, last_saved = review_service.get_review(
        db, workspace_id=workspace.id, local_date=review_date
    )
    groups: OrderedDict[object, ReviewProjectGroupRead] = OrderedDict()
    for step in steps:
        group = groups.setdefault(
            step.project_id,
            ReviewProjectGroupRead(id=step.project.id, name=step.project.name, steps=[]),
        )
        group.steps.append(
            ReviewProjectStepRead(
                id=step.id, planned_date=step.planned_date, name=step.name,
                weight=step.weight, progress=step.progress, comment=step.comment,
                lock_version=step.lock_version,
            )
        )
    return ReviewRead(
        review_date=review_date,
        last_review_saved_at=last_saved,
        tasks=[
            ReviewTaskRead(
                id=task.id, planned_date=task.planned_date,
                name=task.master_task.name, lock_version=task.lock_version,
            )
            for task in tasks
        ],
        pending_items=[
            ReviewPendingItemRead(
                id=item.id, planned_date=item.planned_date, name=item.name,
                progress=item.progress, comment=item.comment,
                lock_version=item.lock_version,
            )
            for item in pending_items
        ],
        projects=list(groups.values()),
    )


@router.patch("", response_model=ReviewSaveResponse)
def save_review(
    review_in: ReviewSave,
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> ReviewSaveResponse:
    try:
        saved_at = review_service.save_review(
            db,
            workspace_id=workspace.id,
            current_user=current_user,
            local_date=local_today(current_user.timezone),
            review_in=review_in,
        )
        db.commit()
    except _DOMAIN_ERRORS as error:
        db.rollback()
        raise _error(error) from error
    except Exception:
        db.rollback()
        raise
    return ReviewSaveResponse(saved_at=saved_at)
