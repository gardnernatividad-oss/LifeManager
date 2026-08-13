from fastapi import APIRouter

from app.api.dependencies import CurrentUser, PersonalWorkspace, SessionDependency
from app.core.dates import local_today
from app.schemas.home import HomeSummary
from app.services import home_service


router = APIRouter(prefix="/home", tags=["Home"])


@router.get("", response_model=HomeSummary)
def get_home_summary(
    db: SessionDependency,
    current_user: CurrentUser,
    workspace: PersonalWorkspace,
) -> HomeSummary:
    return home_service.get_home_summary(
        db,
        workspace_id=workspace.id,
        user_first_name=current_user.first_name,
        local_date=local_today(current_user.timezone),
    )
