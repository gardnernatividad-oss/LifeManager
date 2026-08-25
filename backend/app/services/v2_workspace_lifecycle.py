import uuid

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ActivityMaster,
    ActivityParticipant,
    ActivityReminder,
    Category,
    GenerationBatch,
    MasterTask,
    Notification,
    PendingItem,
    PendingItemHistory,
    Project,
    ProjectLeaderHistory,
    ProjectStage,
    ProjectStageHistory,
    Task,
    User,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
)
from app.models.enums import (
    AccountStatus,
    InvitationStatus,
    MembershipStatus,
    ParticipantCalendarStatus,
    WorkspaceKind,
    WorkspaceLifecycle,
)
from app.schemas.v2_workspace_lifecycle import MemberExitResolution
from app.services.v2_workspace import WorkspaceAccess


class WorkspaceLifecycleNotFoundError(ValueError):
    pass


class WorkspaceLifecyclePermissionError(ValueError):
    pass


class WorkspaceLifecycleConflictError(ValueError):
    pass


BLOCKING_WORKSPACE_MODELS = (
    Category,
    MasterTask,
    ActivityMaster,
    GenerationBatch,
    Task,
    PendingItem,
    PendingItemHistory,
    Project,
    ProjectLeaderHistory,
    ProjectStage,
    ProjectStageHistory,
    Activity,
    ActivityParticipant,
    ActivityReminder,
    WorkspaceInvitation,
    Notification,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _local_date(user: User, instant: datetime) -> date:
    try:
        zone = ZoneInfo(user.timezone or "America/Lima")
    except ZoneInfoNotFoundError as error:
        raise WorkspaceLifecycleConflictError("Account timezone is invalid") from error
    return instant.astimezone(zone).date()


def _lock_owned_shared_workspace(
    db: Session,
    *,
    access: WorkspaceAccess,
    require_active: bool = True,
) -> Workspace:
    predicates = [
        Workspace.id == access.workspace.id,
        Workspace.owner_user_id == access.membership.user_id,
        Workspace.kind == WorkspaceKind.SHARED,
    ]
    if require_active:
        predicates.append(Workspace.lifecycle == WorkspaceLifecycle.ACTIVE)
    workspace = db.scalar(
        select(Workspace).where(*predicates).with_for_update()
    )
    if workspace is None:
        raise WorkspaceLifecyclePermissionError("Active Shared owner required")
    return workspace


def workspace_can_be_hard_deleted(
    db: Session,
    *,
    workspace: Workspace,
) -> bool:
    """Return whether only the owner's structural membership remains."""
    for model in BLOCKING_WORKSPACE_MODELS:
        if db.scalar(
            select(exists().where(model.workspace_id == workspace.id))
        ):
            return False
    meaningful_membership = db.scalar(
        select(
            exists().where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id != workspace.owner_user_id,
            )
        )
    )
    return not bool(meaningful_membership)


def get_workspace_lifecycle(
    db: Session,
    *,
    access: WorkspaceAccess,
) -> tuple[Workspace, bool]:
    workspace = access.workspace
    if workspace.kind != WorkspaceKind.SHARED:
        return workspace, False
    return workspace, workspace_can_be_hard_deleted(db, workspace=workspace)


def resolve_owned_shared_workspace(
    db: Session,
    *,
    account: User,
    workspace_id: uuid.UUID,
) -> WorkspaceAccess:
    row = db.execute(
        select(Workspace, WorkspaceMember)
        .join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Workspace.id,
        )
        .where(
            Workspace.id == workspace_id,
            Workspace.kind == WorkspaceKind.SHARED,
            Workspace.owner_user_id == account.id,
            WorkspaceMember.user_id == account.id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            account.account_status == AccountStatus.ACTIVE,
        )
    ).one_or_none()
    if row is None:
        raise WorkspaceLifecycleNotFoundError("Workspace not found")
    return WorkspaceAccess(workspace=row[0], membership=row[1])


def deactivate_shared_workspace(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
    now: datetime | None = None,
) -> Workspace:
    workspace = _lock_owned_shared_workspace(db, access=owner_access)
    current_time = now or _now()
    pending = list(
        db.scalars(
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace.id,
                WorkspaceInvitation.status == InvitationStatus.PENDING,
            )
            .order_by(WorkspaceInvitation.id)
            .with_for_update()
        ).all()
    )
    for invitation in pending:
        invitation.status = InvitationStatus.CANCELLED
        invitation.cancelled_at = current_time
    workspace.lifecycle = WorkspaceLifecycle.INACTIVE
    workspace.deactivated_at = current_time
    workspace.lock_version += 1
    db.flush()
    return workspace


def reactivate_shared_workspace(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
) -> Workspace:
    workspace = _lock_owned_shared_workspace(
        db,
        access=owner_access,
        require_active=False,
    )
    if workspace.lifecycle != WorkspaceLifecycle.INACTIVE:
        raise WorkspaceLifecycleConflictError("Workspace is already active")
    membership = db.scalar(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == workspace.owner_user_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .with_for_update()
    )
    if membership is None:
        raise WorkspaceLifecycleConflictError("Active owner membership required")
    workspace.lifecycle = WorkspaceLifecycle.ACTIVE
    workspace.deactivated_at = None
    workspace.lock_version += 1
    db.flush()
    return workspace


def hard_delete_shared_workspace(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
) -> None:
    workspace = _lock_owned_shared_workspace(
        db,
        access=owner_access,
        require_active=False,
    )
    if not workspace_can_be_hard_deleted(db, workspace=workspace):
        raise WorkspaceLifecycleConflictError(
            "Workspace contains retained data and can only be deactivated"
        )
    db.delete(workspace)
    db.flush()


def transfer_workspace_ownership(
    db: Session,
    *,
    owner_access: WorkspaceAccess,
    target_user_id: uuid.UUID,
) -> Workspace:
    workspace = _lock_owned_shared_workspace(db, access=owner_access)
    if target_user_id == workspace.owner_user_id:
        raise WorkspaceLifecycleConflictError("Target is already owner")
    row = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            User.account_status == AccountStatus.ACTIVE,
        )
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise WorkspaceLifecycleNotFoundError("Eligible target member not found")
    workspace.owner_user_id = target_user_id
    workspace.lock_version += 1
    db.flush()
    return workspace


def _lock_reassignment_targets(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    departing_user_id: uuid.UUID,
    target_user_ids: set[uuid.UUID],
) -> None:
    if departing_user_id in target_user_ids:
        raise WorkspaceLifecycleConflictError("Departing member cannot be reassignment target")
    if not target_user_ids:
        return
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id.in_(target_user_ids),
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            User.account_status == AccountStatus.ACTIVE,
        )
        .order_by(WorkspaceMember.user_id)
        .with_for_update()
    ).all()
    if {membership.user_id for membership, _ in rows} != target_user_ids:
        raise WorkspaceLifecycleNotFoundError("Eligible reassignment member not found")


def _locked_rows(db: Session, model, *predicates):
    return list(
        db.scalars(
            select(model)
            .where(*predicates)
            .order_by(model.id)
            .with_for_update()
        ).all()
    )


def _apply_directive(
    db: Session,
    *,
    rows: list,
    directive,
    responsible_attribute: str,
) -> None:
    if not rows:
        return
    if directive is None:
        raise WorkspaceLifecycleConflictError("Future responsibilities require resolution")
    if directive.action == "REASSIGN":
        for row in rows:
            setattr(row, responsible_attribute, directive.target_user_id)
            if hasattr(row, "lock_version"):
                row.lock_version += 1
    else:
        for row in rows:
            db.delete(row)


def resolve_member_future_responsibilities(
    db: Session,
    *,
    workspace: Workspace,
    departing_user: User,
    actor_user_id: uuid.UUID,
    resolution: MemberExitResolution | None,
    now: datetime | None = None,
) -> None:
    current_time = now or _now()
    today = _local_date(departing_user, current_time)
    workspace_id = workspace.id
    user_id = departing_user.id

    tasks = _locked_rows(
        db, Task,
        Task.workspace_id == workspace_id,
        Task.responsible_user_id == user_id,
        Task.result.is_(None),
        Task.planned_date > today,
    )
    pending_items = _locked_rows(
        db, PendingItem,
        PendingItem.workspace_id == workspace_id,
        PendingItem.responsible_user_id == user_id,
        PendingItem.is_active.is_(True),
    )
    projects = _locked_rows(
        db, Project,
        Project.workspace_id == workspace_id,
        Project.leader_user_id == user_id,
        Project.is_active.is_(True),
    )
    stages = _locked_rows(
        db, ProjectStage,
        ProjectStage.workspace_id == workspace_id,
        ProjectStage.responsible_user_id == user_id,
        ProjectStage.progress < 100,
        ProjectStage.planned_date > today,
    )

    if resolution is not None and resolution.delete_all:
        from app.schemas.v2_workspace_lifecycle import ResponsibilityDirective
        delete_directive = ResponsibilityDirective(action="DELETE")
        directives = (delete_directive,) * 4
    else:
        directives = (
            resolution.tasks if resolution else None,
            resolution.pending_items if resolution else None,
            resolution.projects if resolution else None,
            resolution.project_stages if resolution else None,
        )

    pending_ids = [row.id for row in pending_items]
    if pending_ids and directives[1] is not None and directives[1].action == "DELETE":
        if db.scalar(select(exists().where(PendingItemHistory.pending_item_id.in_(pending_ids)))):
            raise WorkspaceLifecycleConflictError("Pending history prevents deletion")
    project_ids = [row.id for row in projects]
    if project_ids and directives[2] is not None and directives[2].action == "DELETE":
        if db.scalar(select(exists().where(ProjectLeaderHistory.project_id.in_(project_ids)))) or db.scalar(select(exists().where(ProjectStage.project_id.in_(project_ids)))):
            raise WorkspaceLifecycleConflictError("Project history or stages prevent deletion")
    stage_ids = [row.id for row in stages]
    if stage_ids and directives[3] is not None and directives[3].action == "DELETE":
        if db.scalar(select(exists().where(ProjectStageHistory.project_stage_id.in_(stage_ids)))):
            raise WorkspaceLifecycleConflictError("Project Stage history prevents deletion")

    reassignment_targets = {
        directive.target_user_id
        for rows, directive in zip(
            (tasks, pending_items, projects, stages), directives, strict=True
        )
        if rows and directive is not None and directive.action == "REASSIGN"
    }
    _lock_reassignment_targets(
        db,
        workspace_id=workspace_id,
        departing_user_id=user_id,
        target_user_ids=reassignment_targets,
    )

    project_directive = directives[2]
    if (
        projects
        and project_directive is not None
        and project_directive.action == "REASSIGN"
    ):
        for project in projects:
            db.add(
                ProjectLeaderHistory(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    workspace_id=workspace_id,
                    leader_user_id=project_directive.target_user_id,
                    actor_user_id=actor_user_id,
                    recorded_at=current_time,
                )
            )

    _apply_directive(db, rows=tasks, directive=directives[0], responsible_attribute="responsible_user_id")
    _apply_directive(db, rows=pending_items, directive=directives[1], responsible_attribute="responsible_user_id")
    _apply_directive(db, rows=projects, directive=directives[2], responsible_attribute="leader_user_id")
    _apply_directive(db, rows=stages, directive=directives[3], responsible_attribute="responsible_user_id")

    participants = _locked_rows(
        db, ActivityParticipant,
        ActivityParticipant.workspace_id == workspace_id,
        ActivityParticipant.user_id == user_id,
        ActivityParticipant.calendar_status == ParticipantCalendarStatus.VISIBLE,
        ActivityParticipant.activity_id.in_(
            select(Activity.id).where(
                Activity.workspace_id == workspace_id,
                Activity.starts_at > current_time,
            )
        ),
    )
    for participant in participants:
        participant.calendar_status = ParticipantCalendarStatus.REMOVED
        participant.removed_at = current_time
        participant.lock_version += 1
    reminders = _locked_rows(
        db, ActivityReminder,
        ActivityReminder.workspace_id == workspace_id,
        ActivityReminder.user_id == user_id,
        ActivityReminder.is_enabled.is_(True),
        ActivityReminder.activity_id.in_(
            select(Activity.id).where(
                Activity.workspace_id == workspace_id,
                Activity.starts_at > current_time,
            )
        ),
    )
    for reminder in reminders:
        reminder.is_enabled = False
        reminder.lock_version += 1
