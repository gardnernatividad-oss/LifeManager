import uuid

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings import WeekStartsOn
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole
from app.models.workspace_settings import WorkspaceSettings
from app.schemas.workspace_settings import WorkspaceSettingsReplace
from app.services.workspace import get_workspace_membership


class WorkspaceSettingsNotFoundError(LookupError): pass
class WorkspaceSettingsPermissionError(PermissionError): pass
class WorkspaceSettingsValidationError(ValueError): pass


def _membership(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
    membership = get_workspace_membership(db, workspace_id=workspace_id, user_id=user_id)
    if membership is None: raise WorkspaceSettingsPermissionError("Workspace access denied")
    return membership


def _workspace(db: Session, *, workspace_id: uuid.UUID) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if workspace is None: raise WorkspaceSettingsNotFoundError("Workspace not found")
    return workspace


def _settings(db: Session, *, workspace_id: uuid.UUID) -> WorkspaceSettings | None:
    return db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id))


def _timezone(value: str) -> str:
    try: return ZoneInfo(value.strip()).key
    except (AttributeError, ZoneInfoNotFoundError, ValueError) as error:
        raise WorkspaceSettingsValidationError("timezone must be a valid IANA identifier") from error


def _defaults(workspace: Workspace) -> WorkspaceSettings:
    return WorkspaceSettings(
        workspace_id=workspace.id, timezone=workspace.timezone,
        daily_form_enabled=True, daily_form_reminder_time=time(9),
        daily_task_generation_enabled=True, week_starts_on=WeekStartsOn.MONDAY,
    )


def get_or_create_workspace_settings(db: Session, *, workspace_id: uuid.UUID, current_user: User) -> WorkspaceSettings:
    _membership(db, workspace_id=workspace_id, user_id=current_user.id)
    workspace = _workspace(db, workspace_id=workspace_id)
    settings = _settings(db, workspace_id=workspace_id)
    if settings is None:
        settings = _defaults(workspace); db.add(settings); db.flush()
    return settings


def replace_workspace_settings(db: Session, *, workspace_id: uuid.UUID, current_user: User, settings_in: WorkspaceSettingsReplace) -> WorkspaceSettings:
    membership = _membership(db, workspace_id=workspace_id, user_id=current_user.id)
    if membership.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
        raise WorkspaceSettingsPermissionError("Insufficient workspace permissions")
    workspace = _workspace(db, workspace_id=workspace_id)
    settings = _settings(db, workspace_id=workspace_id)
    if settings is None: settings = _defaults(workspace); db.add(settings)
    values = settings_in.model_dump(); values["timezone"] = _timezone(values["timezone"])
    for field, value in values.items(): setattr(settings, field, value)
    db.flush(); return settings
