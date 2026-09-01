import uuid

from datetime import date

from fastapi import APIRouter

from app.api.v2.dependencies import ActiveWorkspaceMembership, SessionDependency, UsableAccount
from app.api.v2.errors import V2APIError
from app.core.dates import local_today
from app.schemas.v2_report import ActivityReportRead, PendingItemReportRead, ProjectReportRead, ReportCommonFilters, ReportPeriod, ReportSummaryCounts, ReportSummaryRead, TaskReportRead
from app.services.v2_report import get_activity_report, get_pending_item_report, get_project_report, get_report_summary, get_task_report


router = APIRouter(prefix="/workspaces/{workspace_id}/reports", tags=["V2 Reports"])


def _period(date_from: date | None, date_until: date | None) -> ReportPeriod:
    if date_from is not None and date_until is not None and date_from > date_until:
        raise V2APIError(status_code=422, code="INVALID_DATE_RANGE", message="El rango de fechas no es válido.")
    return ReportPeriod(date_from=date_from, date_until=date_until)


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
    _period(date_from, date_until)
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


@router.get("/tasks", response_model=TaskReportRead)
def tasks(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None, master_task_id: uuid.UUID | None = None, custom_tasks: bool | None = None) -> TaskReportRead:
    del account, access
    period = _period(date_from, date_until)
    result = get_task_report(db, workspace_id=workspace_id, date_from=date_from, date_until=date_until, category_id=category_id, responsible_user_id=responsible_user_id, master_task_id=master_task_id, custom_tasks=custom_tasks)
    return TaskReportRead(period=period, filters=ReportCommonFilters(category_id=category_id, responsible_user_id=responsible_user_id), master_task_id=master_task_id, custom_tasks=custom_tasks, **result)


@router.get("/pending-items", response_model=PendingItemReportRead)
def pending_items(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None) -> PendingItemReportRead:
    del access
    period = _period(date_from, date_until)
    result = get_pending_item_report(db, workspace_id=workspace_id, local_date=local_today(account.timezone), date_from=date_from, date_until=date_until, category_id=category_id, responsible_user_id=responsible_user_id)
    return PendingItemReportRead(period=period, filters=ReportCommonFilters(category_id=category_id, responsible_user_id=responsible_user_id), **result)


@router.get("/projects", response_model=ProjectReportRead)
def projects(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None) -> ProjectReportRead:
    del access
    period = _period(date_from, date_until)
    result = get_project_report(db, workspace_id=workspace_id, local_date=local_today(account.timezone), date_from=date_from, date_until=date_until, category_id=category_id, responsible_user_id=responsible_user_id)
    return ProjectReportRead(period=period, filters=ReportCommonFilters(category_id=category_id, responsible_user_id=responsible_user_id), **result)


@router.get("/activities", response_model=ActivityReportRead)
def activities(workspace_id: uuid.UUID, db: SessionDependency, account: UsableAccount, access: ActiveWorkspaceMembership, date_from: date | None = None, date_until: date | None = None, category_id: uuid.UUID | None = None, responsible_user_id: uuid.UUID | None = None, activity_master_id: uuid.UUID | None = None, custom_activities: bool | None = None) -> ActivityReportRead:
    del access
    period = _period(date_from, date_until)
    result = get_activity_report(db, workspace_id=workspace_id, timezone_name=account.timezone, date_from=date_from, date_until=date_until, category_id=category_id, responsible_user_id=responsible_user_id, activity_master_id=activity_master_id, custom_activities=custom_activities)
    return ActivityReportRead(period=period, filters=ReportCommonFilters(category_id=category_id, responsible_user_id=responsible_user_id), activity_master_id=activity_master_id, custom_activities=custom_activities, **result)
