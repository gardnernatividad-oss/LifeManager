import uuid

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, SessionDependency
from app.schemas.workspace_settings import WorkspaceSettingsRead, WorkspaceSettingsReplace
from app.services import workspace_settings_service


router = APIRouter(prefix="/workspaces/{workspace_id}/settings", tags=["Workspace Settings"])


def _raise(error: Exception) -> None:
    if isinstance(error, workspace_settings_service.WorkspaceSettingsNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, workspace_settings_service.WorkspaceSettingsPermissionError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


def _commit(db, operation, **kwargs) -> WorkspaceSettingsRead:
    try:
        settings = operation(db, **kwargs); db.commit(); db.refresh(settings)
    except (
        workspace_settings_service.WorkspaceSettingsNotFoundError,
        workspace_settings_service.WorkspaceSettingsPermissionError,
        workspace_settings_service.WorkspaceSettingsValidationError,
    ) as error:
        db.rollback(); _raise(error)
    except Exception:
        db.rollback(); raise
    return WorkspaceSettingsRead.model_validate(settings)


@router.get("", response_model=WorkspaceSettingsRead)
def get_workspace_settings(workspace_id: uuid.UUID, db: SessionDependency, current_user: CurrentUser) -> WorkspaceSettingsRead:
    return _commit(db, workspace_settings_service.get_or_create_workspace_settings, workspace_id=workspace_id, current_user=current_user)


@router.put("", response_model=WorkspaceSettingsRead)
def replace_workspace_settings(workspace_id: uuid.UUID, settings_in: WorkspaceSettingsReplace, db: SessionDependency, current_user: CurrentUser) -> WorkspaceSettingsRead:
    return _commit(db, workspace_settings_service.replace_workspace_settings, workspace_id=workspace_id, current_user=current_user, settings_in=settings_in)
