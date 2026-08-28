import uuid

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import MasterTask, PendingItem, Project, ProjectStage, Task, Workspace, WorkspaceMember
from app.models.enums import MembershipStatus, WorkspaceLifecycle


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
