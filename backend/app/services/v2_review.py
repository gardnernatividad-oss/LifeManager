import uuid

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import MasterTask, PendingItem, Project, ProjectStage, Task, Workspace, WorkspaceMember
from app.models.enums import MembershipStatus, TaskResult, WorkspaceLifecycle
from app.schemas.v2_review import ReviewPendingItemChange, ReviewProjectStageChange, ReviewTaskChange
from app.services.v2_pending_item import update_pending_progress
from app.services.v2_project_stage import update_project_stage_progress
from app.services.v2_task import resolve_task
from app.services.v2_workspace import WorkspaceAccess


class ReviewNotFoundError(LookupError):
    pass


class ReviewConflictError(ValueError):
    pass


@dataclass(frozen=True)
class GlobalReviewSelection:
    tasks: list[tuple[Task, MasterTask, Workspace]]
    pending_items: list[tuple[PendingItem, Workspace]]
    project_stages: list[tuple[ProjectStage, Project, Workspace]]


def get_global_review(
    db: Session, *, user_id: uuid.UUID, local_date: date,
) -> GlobalReviewSelection:
    active_membership = and_(
        WorkspaceMember.workspace_id == Workspace.id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == MembershipStatus.ACTIVE,
    )
    active_workspace = Workspace.lifecycle == WorkspaceLifecycle.ACTIVE

    tasks = list(db.execute(
        select(Task, MasterTask, Workspace)
        .join(MasterTask, and_(MasterTask.id == Task.master_task_id, MasterTask.workspace_id == Task.workspace_id))
        .join(Workspace, Workspace.id == Task.workspace_id)
        .join(WorkspaceMember, active_membership)
        .where(
            active_workspace,
            Task.responsible_user_id == user_id,
            Task.result.is_(None),
            Task.planned_date <= local_date,
        )
        .order_by(Task.planned_date, Workspace.name, MasterTask.name, Task.id)
    ).all())
    pending_items = list(db.execute(
        select(PendingItem, Workspace)
        .join(Workspace, Workspace.id == PendingItem.workspace_id)
        .join(WorkspaceMember, active_membership)
        .where(
            active_workspace,
            PendingItem.responsible_user_id == user_id,
            PendingItem.is_active.is_(True),
            PendingItem.progress < 100,
            PendingItem.planned_date.is_not(None),
            PendingItem.planned_date <= local_date,
        )
        .order_by(PendingItem.planned_date, Workspace.name, PendingItem.name, PendingItem.id)
    ).all())
    project_stages = list(db.execute(
        select(ProjectStage, Project, Workspace)
        .join(Project, and_(Project.id == ProjectStage.project_id, Project.workspace_id == ProjectStage.workspace_id))
        .join(Workspace, Workspace.id == Project.workspace_id)
        .join(WorkspaceMember, active_membership)
        .where(
            active_workspace,
            Project.is_active.is_(True),
            ProjectStage.responsible_user_id == user_id,
            ProjectStage.progress < 100,
            ProjectStage.planned_date <= local_date,
        )
        .order_by(ProjectStage.planned_date, Workspace.name, Project.name, ProjectStage.position, ProjectStage.id)
    ).all())
    return GlobalReviewSelection(tasks=tasks, pending_items=pending_items, project_stages=project_stages)


def _require_unique(ids: list[uuid.UUID]) -> None:
    if len(ids) != len(set(ids)):
        raise ReviewConflictError("Review batch contains duplicate items")


def _lock_accesses(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_ids: set[uuid.UUID],
) -> dict[uuid.UUID, WorkspaceAccess]:
    ordered_ids = sorted(workspace_ids, key=str)
    workspaces = list(db.scalars(
        select(Workspace)
        .where(Workspace.id.in_(ordered_ids), Workspace.lifecycle == WorkspaceLifecycle.ACTIVE)
        .order_by(Workspace.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all())
    memberships = list(db.scalars(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id.in_(ordered_ids),
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
        )
        .order_by(WorkspaceMember.workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all())
    workspace_by_id = {workspace.id: workspace for workspace in workspaces}
    membership_by_workspace = {membership.workspace_id: membership for membership in memberships}
    if set(workspace_by_id) != workspace_ids or set(membership_by_workspace) != workspace_ids:
        raise ReviewNotFoundError("Review item unavailable")
    return {
        workspace_id: WorkspaceAccess(
            workspace=workspace_by_id[workspace_id],
            membership=membership_by_workspace[workspace_id],
        )
        for workspace_id in workspace_ids
    }


def save_review_tasks(
    db: Session,
    *,
    actor,
    changes: list[ReviewTaskChange],
    local_date: date,
) -> list[Task]:
    ids = [change.task_id for change in changes]
    _require_unique(ids)
    identified = db.execute(
        select(Task.id, Task.workspace_id).where(Task.id.in_(ids))
    ).all()
    if len(identified) != len(ids):
        raise ReviewNotFoundError("Review Task unavailable")
    workspace_by_id = {task_id: workspace_id for task_id, workspace_id in identified}
    accesses = _lock_accesses(db, user_id=actor.id, workspace_ids=set(workspace_by_id.values()))
    saved: list[Task] = []
    for change in sorted(changes, key=lambda item: str(item.task_id)):
        try:
            saved.append(resolve_task(
                db,
                access=accesses[workspace_by_id[change.task_id]],
                actor=actor,
                task_id=change.task_id,
                expected_version=change.lock_version,
                result=TaskResult(change.result),
                local_date=local_date,
            ))
        except (LookupError, ValueError) as error:
            raise ReviewConflictError("Review Task changed") from error
    return saved


def save_review_pending_items(
    db: Session,
    *,
    actor,
    changes: list[ReviewPendingItemChange],
    local_date: date,
) -> list[PendingItem]:
    ids = [change.pending_item_id for change in changes]
    _require_unique(ids)
    identified = db.execute(
        select(PendingItem.id, PendingItem.workspace_id).where(PendingItem.id.in_(ids))
    ).all()
    if len(identified) != len(ids):
        raise ReviewNotFoundError("Review Pending Item unavailable")
    workspace_by_id = {item_id: workspace_id for item_id, workspace_id in identified}
    accesses = _lock_accesses(db, user_id=actor.id, workspace_ids=set(workspace_by_id.values()))
    saved: list[PendingItem] = []
    for change in sorted(changes, key=lambda item: str(item.pending_item_id)):
        try:
            saved.append(update_pending_progress(
                db,
                access=accesses[workspace_by_id[change.pending_item_id]],
                actor=actor,
                pending_item_id=change.pending_item_id,
                progress=change.progress,
                expected_version=change.lock_version,
                local_date=local_date,
                comment=change.comment,
                review_eligible_date=local_date,
            ))
        except (LookupError, ValueError) as error:
            raise ReviewConflictError("Review Pending Item changed") from error
    return saved


def save_review_project_stages(
    db: Session,
    *,
    actor,
    changes: list[ReviewProjectStageChange],
    local_date: date,
) -> list[ProjectStage]:
    ids = [change.stage_id for change in changes]
    _require_unique(ids)
    identified = db.execute(
        select(ProjectStage.id, ProjectStage.workspace_id, ProjectStage.project_id)
        .where(ProjectStage.id.in_(ids))
    ).all()
    if len(identified) != len(ids):
        raise ReviewNotFoundError("Review Stage unavailable")
    context_by_id = {
        stage_id: (workspace_id, project_id)
        for stage_id, workspace_id, project_id in identified
    }
    accesses = _lock_accesses(
        db,
        user_id=actor.id,
        workspace_ids={context[0] for context in context_by_id.values()},
    )
    base_versions: dict[uuid.UUID, int] = {}
    updates_by_project: dict[uuid.UUID, int] = {}
    for change in changes:
        project_id = context_by_id[change.stage_id][1]
        previous = base_versions.setdefault(project_id, change.project_lock_version)
        if previous != change.project_lock_version:
            raise ReviewConflictError("Review Project versions disagree")
    saved: list[ProjectStage] = []
    for change in sorted(changes, key=lambda item: (
        str(context_by_id[item.stage_id][1]), str(item.stage_id)
    )):
        workspace_id, project_id = context_by_id[change.stage_id]
        offset = updates_by_project.get(project_id, 0)
        try:
            saved.append(update_project_stage_progress(
                db,
                access=accesses[workspace_id],
                actor=actor,
                project_id=project_id,
                stage_id=change.stage_id,
                progress=change.progress,
                comment=change.comment,
                expected_version=change.lock_version,
                project_version=base_versions[project_id] + offset,
                local_date=local_date,
                review_eligible_date=local_date,
            ))
        except (LookupError, ValueError) as error:
            raise ReviewConflictError("Review Stage changed") from error
        updates_by_project[project_id] = offset + 1
    return saved
