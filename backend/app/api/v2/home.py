from datetime import datetime, timezone

from fastapi import APIRouter

from app.api.v2.dependencies import SessionDependency, UsableAccount
from app.schemas.v2_home import HomeAttentionItem, HomeSummaryRead, HomeTodayCounts, HomeUpcomingActivity, HomeUpcomingDay, HomeWorkspace
from app.services.v2_home import get_home_summary


router = APIRouter(prefix="/home", tags=["V2 Home"])


def _workspace(workspace) -> HomeWorkspace:
    return HomeWorkspace(id=workspace.id, name=workspace.name, color=workspace.color, icon=workspace.icon)


@router.get("", response_model=HomeSummaryRead)
def read_home(db: SessionDependency, account: UsableAccount) -> HomeSummaryRead:
    result = get_home_summary(db, user_id=account.id, timezone_name=account.timezone, now=datetime.now(timezone.utc))
    return HomeSummaryRead(
        local_date=result.local_date,
        today=HomeTodayCounts(tasks=result.today[0], pending_items=result.today[1], project_stages=result.today[2], activities=result.today[3]),
        upcoming_activities=[HomeUpcomingActivity(id=item.activity.id, workspace=_workspace(item.workspace), name=item.master.name if item.master is not None else item.activity.custom_name, starts_at=item.activity.starts_at, ends_at=item.activity.ends_at) for item in result.upcoming_activities],
        attention=[HomeAttentionItem(type=item.type, id=item.id, workspace=_workspace(item.workspace), name=item.name, planned_date=item.planned_date, project_id=item.project_id) for item in result.attention],
        upcoming_days=[HomeUpcomingDay(date=day, tasks=tasks, pending_items=pending, project_stages=stages, activities=activities) for day, tasks, pending, stages, activities in result.upcoming_days],
    )
