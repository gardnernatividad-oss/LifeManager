import uuid

from datetime import date

from fastapi import APIRouter

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.schemas.v2_report import ReportSummaryCounts, ReportSummaryRead
from app.services.v2_report import get_report_summary


router = APIRouter(prefix="/workspaces/{workspace_id}/reports", tags=["V2 Reports"])


@router.get("/summary", response_model=ReportSummaryRead)
def summary(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    account: UsableAccount,
    access: ActiveWorkspaceMembership,
    date_from: date | None = None,
    date_until: date | None = None,
    category_id: uuid.UUID | None = None,
    responsible_user_id: uuid.UUID | None = None,
) -> ReportSummaryRead:
    del access
    if date_from is not None and date_until is not None and date_from > date_until:
        raise V2APIError(status_code=422, code="INVALID_DATE_RANGE", message="El rango de fechas no es válido.")
    result = get_report_summary(
        db,
        workspace_id=workspace_id,
        timezone_name=account.timezone,
        date_from=date_from,
        date_until=date_until,
        category_id=category_id,
        responsible_user_id=responsible_user_id,
    )
    return ReportSummaryRead(
        local_date=local_today(account.timezone),
        date_from=date_from,
        date_until=date_until,
        category_id=category_id,
        responsible_user_id=responsible_user_id,
        counts=ReportSummaryCounts(
            tasks=result.tasks,
            pending_items=result.pending_items,
            projects=result.projects,
            activities=result.activities,
            total=result.total,
        ),
    )
