import uuid

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, CalendarVisibility, MembershipStatus, WorkspaceKind, WorkspaceLifecycle
from app.services.v2_calendar import CalendarActivityProjection, list_my_calendar


class CalendarComparisonNotFoundError(ValueError):
    pass


class CalendarVisibilityConflictError(ValueError):
    pass


@dataclass(frozen=True)
class BusyBlock:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class CalendarComparison:
    visibility: CalendarVisibility
    events: list[CalendarActivityProjection]
    busy_blocks: list[BusyBlock]


def _lock_comparison_context(
    db: Session, *, workspace_id: uuid.UUID, viewer_id: uuid.UUID, target_id: uuid.UUID,
) -> WorkspaceMember:
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.kind == WorkspaceKind.SHARED,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
        ).with_for_update(read=True)
    )
    if workspace is None or viewer_id == target_id:
        raise CalendarComparisonNotFoundError("Calendar comparison not found")
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id.in_([viewer_id, target_id]),
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            User.account_status == AccountStatus.ACTIVE,
        )
        .order_by(WorkspaceMember.user_id)
        .with_for_update(read=True, of=WorkspaceMember)
    ).all()
    if len(rows) != 2:
        raise CalendarComparisonNotFoundError("Calendar comparison not found")
    memberships = {membership.user_id: membership for membership, _ in rows}
    if viewer_id not in memberships or target_id not in memberships:
        raise CalendarComparisonNotFoundError("Calendar comparison not found")
    return memberships[target_id]


def _merge_busy(events: list[CalendarActivityProjection]) -> list[BusyBlock]:
    merged: list[BusyBlock] = []
    for projection in events:
        start, end = projection.activity.starts_at, projection.activity.ends_at
        if merged and start <= merged[-1].ends_at:
            if end > merged[-1].ends_at:
                merged[-1] = BusyBlock(merged[-1].starts_at, end)
        else:
            merged.append(BusyBlock(start, end))
    return merged


def compare_calendar(
    db: Session, *, workspace_id: uuid.UUID, viewer_id: uuid.UUID, target_id: uuid.UUID,
    range_start: datetime, range_end: datetime, now: datetime,
) -> CalendarComparison:
    target_membership = _lock_comparison_context(
        db, workspace_id=workspace_id, viewer_id=viewer_id, target_id=target_id,
    )
    visibility = target_membership.calendar_visibility
    if visibility == CalendarVisibility.HIDE:
        return CalendarComparison(visibility=visibility, events=[], busy_blocks=[])
    events = list_my_calendar(
        db, user_id=target_id, range_start=range_start, range_end=range_end, now=now,
    )
    if visibility == CalendarVisibility.AVAILABILITY_ONLY:
        return CalendarComparison(visibility=visibility, events=[], busy_blocks=_merge_busy(events))
    return CalendarComparison(visibility=visibility, events=events, busy_blocks=[])


def get_calendar_visibility(db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
    membership = db.scalar(select(WorkspaceMember).join(Workspace).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == MembershipStatus.ACTIVE,
        Workspace.kind == WorkspaceKind.SHARED,
        Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
    ))
    if membership is None:
        raise CalendarComparisonNotFoundError("Calendar visibility not found")
    return membership


def update_calendar_visibility(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID,
    visibility: CalendarVisibility, expected_lock_version: int,
) -> WorkspaceMember:
    workspace = db.scalar(select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.kind == WorkspaceKind.SHARED,
        Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
    ).with_for_update())
    if workspace is None:
        raise CalendarComparisonNotFoundError("Calendar visibility not found")
    membership = db.scalar(
        select(WorkspaceMember).join(Workspace).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MembershipStatus.ACTIVE,
            Workspace.kind == WorkspaceKind.SHARED,
            Workspace.lifecycle == WorkspaceLifecycle.ACTIVE,
        ).with_for_update(of=WorkspaceMember).execution_options(populate_existing=True)
    )
    if membership is None:
        raise CalendarComparisonNotFoundError("Calendar visibility not found")
    if membership.lock_version != expected_lock_version:
        raise CalendarVisibilityConflictError("Stale calendar visibility")
    membership.calendar_visibility = visibility
    membership.lock_version += 1
    db.flush()
    return membership
