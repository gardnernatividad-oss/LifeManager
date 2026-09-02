from fastapi import APIRouter

from app.api.v2.identity import router as identity_router
from app.api.v2.workspaces import router as workspace_router
from app.api.v2.workspace_invitations import router as invitation_router
from app.api.v2.workspace_members import router as member_router
from app.api.v2.workspace_lifecycle import router as lifecycle_router
from app.api.v2.catalogs import router as catalog_router
from app.api.v2.tasks import router as task_router
from app.api.v2.pending_items import router as pending_item_router
from app.api.v2.projects import router as project_router
from app.api.v2.project_stages import router as project_stage_router
from app.api.v2.activities import router as activity_router
from app.api.v2.calendar import router as calendar_router
from app.api.v2.calendar_comparison import router as calendar_comparison_router
from app.api.v2.review import router as review_router
from app.api.v2.home import router as home_router
from app.api.v2.notifications import router as notification_router
from app.api.v2.reports import router as report_router
from app.api.v2.configuration import router as configuration_router
from app.api.v2.admin import router as admin_router


api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(workspace_router)
api_router.include_router(invitation_router)
api_router.include_router(member_router)
api_router.include_router(lifecycle_router)
api_router.include_router(catalog_router)
api_router.include_router(task_router)
api_router.include_router(pending_item_router)
api_router.include_router(project_router)
api_router.include_router(project_stage_router)
api_router.include_router(activity_router)
api_router.include_router(calendar_router)
api_router.include_router(calendar_comparison_router)
api_router.include_router(review_router)
api_router.include_router(home_router)
api_router.include_router(notification_router)
api_router.include_router(report_router)
api_router.include_router(configuration_router)
api_router.include_router(admin_router)
