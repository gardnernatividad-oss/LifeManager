"""Small, composable factories for the LifeManager V2 persistence model.

The caller owns the transaction. ``V2Factory`` only adds objects to the
provided session; scenario builders flush so database-generated values and
deferred invariants can be inspected, but never commit or roll back.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Activity,
    ActivityMaster,
    ActivityParticipant,
    ActivityReminder,
    Category,
    GenerationBatch,
    MasterTask,
    Notification,
    NotificationDelivery,
    PendingItem,
    PendingItemHistory,
    Project,
    ProjectLeaderHistory,
    ProjectStage,
    ProjectStageHistory,
    PushSubscription,
    ReminderPreference,
    Task,
    User,
    UserReviewMetadata,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
)
from app.models.enums import (
    AccountStatus,
    ActivityStatus,
    CalendarVisibility,
    DeliveryStatus,
    GenerationEntityType,
    GenerationPattern,
    GlobalRole,
    HistoryEventType,
    InvitationStatus,
    MembershipStatus,
    NotificationType,
    ParticipantCalendarStatus,
    ReminderType,
    ScheduleKind,
    TaskResult,
    WorkspaceKind,
)

UTC = timezone.utc
DEFAULT_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
DEFAULT_TODAY = date(2026, 1, 15)
TEST_PASSWORD = "Fixture-only password 123!"
_NAMESPACE = uuid.UUID("4ac4e668-405f-4f40-a910-041818efac48")


def normalized_name(value: str) -> str:
    cleaned = " ".join(value.split())
    return unicodedata.normalize("NFC", cleaned).casefold()


@dataclass(frozen=True)
class PersonalWorkspaceScenario:
    user: User
    workspace: Workspace
    owner_membership: WorkspaceMember


@dataclass(frozen=True)
class SharedWorkspaceScenario:
    owner: User
    members: tuple[User, User, User]
    workspace: Workspace
    memberships: tuple[WorkspaceMember, WorkspaceMember, WorkspaceMember, WorkspaceMember]


@dataclass(frozen=True)
class CanonicalV2Dataset:
    users: tuple[User, ...]
    personal_workspaces: tuple[PersonalWorkspaceScenario, ...]
    shared_workspace: SharedWorkspaceScenario
    categories: tuple[Category, ...]
    master_tasks: tuple[MasterTask, ...]
    activity_masters: tuple[ActivityMaster, ...]
    generation_batches: tuple[GenerationBatch, ...]
    tasks: tuple[Task, ...]
    pending_items: tuple[PendingItem, ...]
    pending_history: tuple[PendingItemHistory, ...]
    projects: tuple[Project, ...]
    project_stages: tuple[ProjectStage, ...]
    project_stage_history: tuple[ProjectStageHistory, ...]
    activities: tuple[Activity, ...]
    participants: tuple[ActivityParticipant, ...]
    activity_reminders: tuple[ActivityReminder, ...]
    review_metadata: tuple[UserReviewMetadata, ...]
    reminder_preferences: tuple[ReminderPreference, ...]
    notifications: tuple[Notification, ...]
    push_subscriptions: tuple[PushSubscription, ...]
    deliveries: tuple[NotificationDelivery, ...]


class V2Factory:
    """Construct valid V2 records using an externally managed session."""

    def __init__(self, db: Session, *, namespace: uuid.UUID = _NAMESPACE) -> None:
        self.db = db
        self.namespace = namespace
        self._sequence = 0
        self._password_hash: str | None = None

    def _id(self, label: str) -> uuid.UUID:
        self._sequence += 1
        return uuid.uuid5(self.namespace, f"{self._sequence}:{label}")

    def _add(self, value):
        self.db.add(value)
        return value

    def user(
        self,
        label: str,
        *,
        status: AccountStatus = AccountStatus.ACTIVE,
        global_admin: bool = False,
    ) -> User:
        if self._password_hash is None:
            self._password_hash = hash_password(TEST_PASSWORD)
        verified_at = DEFAULT_NOW if status is not AccountStatus.PENDING_EMAIL_VERIFICATION else None
        return self._add(User(
            id=self._id(f"user:{label}"),
            email=f"{normalized_name(label).replace(' ', '-')}@example.test",
            hashed_password=self._password_hash,
            first_name=label.title(),
            last_name="Test",
            timezone="America/Lima",
            account_status=status,
            global_role=GlobalRole.GLOBAL_ADMIN if global_admin else None,
            email_verified_at=verified_at,
            status_changed_at=DEFAULT_NOW,
        ))

    def workspace(self, owner: User, name: str, *, kind: WorkspaceKind) -> Workspace:
        return self._add(Workspace(id=self._id(f"workspace:{name}"), name=name, kind=kind, owner_user_id=owner.id))

    def membership(
        self,
        workspace: Workspace,
        user: User,
        *,
        status: MembershipStatus = MembershipStatus.ACTIVE,
        visibility: CalendarVisibility = CalendarVisibility.HIDE,
    ) -> WorkspaceMember:
        ended_at = None if status is MembershipStatus.ACTIVE else DEFAULT_NOW
        return self._add(WorkspaceMember(
            id=self._id(f"membership:{workspace.name}:{user.email}"),
            workspace_id=workspace.id,
            user_id=user.id,
            status=status,
            calendar_visibility=visibility,
            joined_at=DEFAULT_NOW - timedelta(days=30),
            ended_at=ended_at,
        ))

    def personal_workspace(
        self, *, label: str = "owner", user: User | None = None,
    ) -> PersonalWorkspaceScenario:
        owner = user or self.user(label)
        workspace = self.workspace(owner, f"{label.title()} Personal", kind=WorkspaceKind.PERSONAL)
        membership = self.membership(workspace, owner, visibility=CalendarVisibility.SHOW_DETAILS)
        self.db.flush()
        return PersonalWorkspaceScenario(owner, workspace, membership)

    def shared_workspace(
        self, *, owner: User | None = None,
        members: tuple[User, User, User] | None = None,
    ) -> SharedWorkspaceScenario:
        owner = owner or self.user("shared-owner")
        members = members or (self.user("member-a"), self.user("member-b"), self.user("member-c"))
        workspace = self.workspace(owner, "Shared Test Home", kind=WorkspaceKind.SHARED)
        memberships = (
            self.membership(workspace, owner, visibility=CalendarVisibility.SHOW_DETAILS),
            self.membership(workspace, members[0], visibility=CalendarVisibility.SHOW_DETAILS),
            self.membership(workspace, members[1], visibility=CalendarVisibility.AVAILABILITY_ONLY),
            self.membership(workspace, members[2], visibility=CalendarVisibility.HIDE),
        )
        self.db.flush()
        return SharedWorkspaceScenario(owner, members, workspace, memberships)

    def category(self, workspace: Workspace, name: str, *, active: bool = True) -> Category:
        clean = " ".join(name.split())
        return self._add(Category(
            id=self._id(f"category:{workspace.id}:{clean}"), workspace_id=workspace.id,
            name=clean, normalized_name=normalized_name(clean), is_active=active,
        ))

    def master_task(self, workspace: Workspace, category: Category, name: str, *, active: bool = True) -> MasterTask:
        clean = " ".join(name.split())
        return self._add(MasterTask(
            id=self._id(f"master-task:{workspace.id}:{clean}"), workspace_id=workspace.id,
            category_id=category.id, name=clean, normalized_name=normalized_name(clean), is_active=active,
        ))

    def activity_master(self, workspace: Workspace, category: Category, name: str, *, active: bool = True) -> ActivityMaster:
        clean = " ".join(name.split())
        return self._add(ActivityMaster(
            id=self._id(f"activity-master:{workspace.id}:{clean}"), workspace_id=workspace.id,
            category_id=category.id, name=clean, normalized_name=normalized_name(clean), is_active=active,
        ))

    def generation_batch(
        self, workspace: Workspace, creator: User, *, entity_type: GenerationEntityType,
        pattern: GenerationPattern, date_from: date, date_until: date,
        weekdays: list[int] | None = None, month_days: list[int] | None = None,
    ) -> GenerationBatch:
        return self._add(GenerationBatch(
            id=self._id(f"batch:{entity_type}:{pattern}"), workspace_id=workspace.id,
            entity_type=entity_type, pattern=pattern, date_from=date_from, date_until=date_until,
            weekdays=weekdays, month_days=month_days,
            timezone="America/Lima" if entity_type is GenerationEntityType.ACTIVITY else None,
            created_by_user_id=creator.id, created_at=DEFAULT_NOW,
        ))

    def task(
        self, workspace: Workspace, master: MasterTask, responsible: User, creator: User,
        planned_date: date, *, result: TaskResult | None = None,
        batch: GenerationBatch | None = None,
    ) -> Task:
        resolved = result is not None
        return self._add(Task(
            id=self._id(f"task:{workspace.id}:{master.id}:{responsible.id}:{planned_date}"),
            workspace_id=workspace.id, master_task_id=master.id,
            responsible_user_id=responsible.id, planned_date=planned_date, result=result,
            resolved_at=DEFAULT_NOW if resolved else None,
            resolved_by_user_id=responsible.id if resolved else None,
            created_by_user_id=creator.id,
            generation_batch_id=batch.id if batch else None,
        ))

    def pending_item(
        self, workspace: Workspace, category: Category, responsible: User, creator: User,
        name: str, *, progress: int = 0, active: bool = True,
        planned_date: date | None = DEFAULT_TODAY,
    ) -> PendingItem:
        effective_date = planned_date if active else None
        return self._add(PendingItem(
            id=self._id(f"pending:{workspace.id}:{name}"), workspace_id=workspace.id,
            category_id=category.id, responsible_user_id=responsible.id, name=name,
            is_active=active, planned_date=effective_date, progress=progress,
            completion_date=DEFAULT_TODAY if progress == 100 else None,
            created_by_user_id=creator.id,
        ))

    def pending_history(
        self, item: PendingItem, actor: User, progress: int, *, comment: str | None,
        recorded_at: datetime, event_type: HistoryEventType = HistoryEventType.TRACKING,
    ) -> PendingItemHistory:
        return self._add(PendingItemHistory(
            id=self._id(f"pending-history:{item.id}:{recorded_at.isoformat()}"),
            pending_item_id=item.id, workspace_id=item.workspace_id, actor_user_id=actor.id,
            progress=progress, comment=comment, event_type=event_type, recorded_at=recorded_at,
        ))

    def project(
        self, workspace: Workspace, category: Category, leader: User, creator: User,
        name: str, *, active: bool = True,
    ) -> Project:
        return self._add(Project(
            id=self._id(f"project:{workspace.id}:{name}"), workspace_id=workspace.id,
            category_id=category.id, leader_user_id=leader.id, name=name,
            description="Fixture project", is_active=active, created_by_user_id=creator.id,
        ))

    def project_stage(
        self, project: Project, responsible: User, name: str, *, position: int,
        weight: Decimal, progress: int, planned_date: date,
    ) -> ProjectStage:
        return self._add(ProjectStage(
            id=self._id(f"stage:{project.id}:{position}"), workspace_id=project.workspace_id,
            project_id=project.id, responsible_user_id=responsible.id, name=name,
            position=position, weight=weight, planned_date=planned_date, progress=progress,
            completion_date=DEFAULT_TODAY if progress == 100 else None,
        ))

    def project_stage_history(
        self, stage: ProjectStage, actor: User, progress: int, *, comment: str,
        recorded_at: datetime,
    ) -> ProjectStageHistory:
        return self._add(ProjectStageHistory(
            id=self._id(f"stage-history:{stage.id}:{recorded_at.isoformat()}"),
            project_stage_id=stage.id, workspace_id=stage.workspace_id,
            actor_user_id=actor.id, progress=progress, comment=comment,
            event_type=HistoryEventType.TRACKING, recorded_at=recorded_at,
        ))

    def activity(
        self, workspace: Workspace, organizer: User, title: str, *, starts_at: datetime,
        activity_master: ActivityMaster | None = None, custom_category: Category | None = None,
        batch: GenerationBatch | None = None, cancelled: bool = False,
    ) -> Activity:
        return self._add(Activity(
            id=self._id(f"activity:{workspace.id}:{title}:{starts_at.isoformat()}"),
            workspace_id=workspace.id, organizer_user_id=organizer.id,
            activity_master_id=activity_master.id if activity_master else None,
            title=title, custom_category_id=custom_category.id if custom_category else None,
            starts_at=starts_at, ends_at=starts_at + timedelta(hours=1),
            status=ActivityStatus.CANCELLED if cancelled else ActivityStatus.SCHEDULED,
            cancelled_at=DEFAULT_NOW if cancelled else None,
            cancelled_by_user_id=organizer.id if cancelled else None,
            generation_batch_id=batch.id if batch else None,
        ))

    def participant(
        self, activity: Activity, user: User, *, removed: bool = False,
    ) -> ActivityParticipant:
        return self._add(ActivityParticipant(
            id=self._id(f"participant:{activity.id}:{user.id}"), activity_id=activity.id,
            workspace_id=activity.workspace_id, user_id=user.id,
            calendar_status=ParticipantCalendarStatus.REMOVED if removed else ParticipantCalendarStatus.VISIBLE,
            removed_at=DEFAULT_NOW if removed else None,
        ))

    def activity_reminder(
        self, activity: Activity, user: User, *, enabled: bool = True,
    ) -> ActivityReminder:
        return self._add(ActivityReminder(
            id=self._id(f"activity-reminder:{activity.id}:{user.id}"),
            activity_id=activity.id, workspace_id=activity.workspace_id, user_id=user.id,
            minutes_before=30, is_enabled=enabled,
        ))

    def review_metadata(self, user: User, *, offset: int) -> UserReviewMetadata:
        instant = DEFAULT_NOW - timedelta(hours=offset)
        return self._add(UserReviewMetadata(
            user_id=user.id, tasks_last_saved_at=instant,
            pending_items_last_saved_at=instant - timedelta(minutes=10),
            project_stages_last_saved_at=instant - timedelta(minutes=20),
            updated_at=instant,
        ))

    def reminder_preference(
        self, user: User, reminder_type: ReminderType, *, local_time: time,
        schedule_kind: ScheduleKind, weekdays: list[int] | None = None,
        month_days: list[int] | None = None,
    ) -> ReminderPreference:
        return self._add(ReminderPreference(
            id=self._id(f"preference:{user.id}:{reminder_type}"), user_id=user.id,
            reminder_type=reminder_type, is_enabled=True, schedule_kind=schedule_kind,
            local_time=local_time, weekdays=weekdays, month_days=month_days,
        ))

    def notification(
        self, recipient: User, notification_type: NotificationType, *, workspace: Workspace | None,
        actor: User | None = None, read: bool = False, label: str | None = None,
    ) -> Notification:
        suffix = label or notification_type.value
        return self._add(Notification(
            id=self._id(f"notification:{recipient.id}:{suffix}"), recipient_user_id=recipient.id,
            actor_user_id=actor.id if actor else None, workspace_id=workspace.id if workspace else None,
            notification_type=notification_type, title="Fixture notification",
            body="Safe fixture-only notification body.", deep_link="/test/resource",
            payload={"fixture": True, "resource_id": str(workspace.id) if workspace else None},
            dedup_key=f"fixture:{recipient.id}:{suffix}", read_at=DEFAULT_NOW if read else None,
            created_at=DEFAULT_NOW,
        ))

    def push_subscription(self, user: User, *, active: bool = True, label: str = "default") -> PushSubscription:
        digest = hashlib.sha256(f"fixture:{user.id}:{label}".encode()).digest()
        return self._add(PushSubscription(
            id=self._id(f"subscription:{user.id}:{label}"), user_id=user.id,
            endpoint_ciphertext=b"fixture-encrypted-endpoint", endpoint_hash=digest,
            p256dh_ciphertext=b"fixture-encrypted-p256dh", auth_ciphertext=b"fixture-encrypted-auth",
            user_agent="LifeManager fixture agent", is_active=active,
            invalidated_at=None if active else DEFAULT_NOW,
        ))

    def delivery(
        self, notification: Notification, subscription: PushSubscription, status: DeliveryStatus,
    ) -> NotificationDelivery:
        return self._add(NotificationDelivery(
            id=self._id(f"delivery:{notification.id}:{subscription.id}"),
            notification_id=notification.id, push_subscription_id=subscription.id,
            status=status, attempt_count=1 if status is not DeliveryStatus.PENDING else 0,
            delivered_at=DEFAULT_NOW if status is DeliveryStatus.DELIVERED else None,
            last_error_code="fixture_failure" if status is DeliveryStatus.FAILED else None,
            created_at=DEFAULT_NOW, updated_at=DEFAULT_NOW,
        ))

    def invitation(
        self, workspace: Workspace, inviter: User, *, status: InvitationStatus,
        recipient: User | None = None,
    ) -> WorkspaceInvitation:
        terminal = status in {InvitationStatus.ACCEPTED, InvitationStatus.REJECTED, InvitationStatus.EXPIRED}
        cancelled = status is InvitationStatus.CANCELLED
        return self._add(WorkspaceInvitation(
            id=self._id(f"invitation:{workspace.id}:{status}"), workspace_id=workspace.id,
            recipient_email=recipient.email if recipient else "invitee@example.test",
            recipient_user_id=recipient.id if recipient else None, inviter_user_id=inviter.id,
            status=status, token_digest=hashlib.sha256(f"fixture:{status}".encode()).digest(),
            expires_at=DEFAULT_NOW + timedelta(days=7),
            responded_at=DEFAULT_NOW if terminal else None,
            cancelled_at=DEFAULT_NOW if cancelled else None, created_at=DEFAULT_NOW,
        ))

    def build_canonical_dataset(self) -> CanonicalV2Dataset:
        personal_a = self.personal_workspace(label="user-a")
        personal_b = self.personal_workspace(label="user-b")
        personal_c = self.personal_workspace(label="user-c")
        member_d = self.user("member-d")
        shared = self.shared_workspace(
            owner=personal_a.user,
            members=(personal_b.user, personal_c.user, member_d),
        )
        owner, member_a, member_b, member_c = (shared.owner, *shared.members)

        categories = (
            self.category(shared.workspace, "Personal"),
            self.category(shared.workspace, "Trabajo"),
            self.category(shared.workspace, "Alimentación"),
            self.category(shared.workspace, "Deporte", active=False),
            self.category(personal_a.workspace, "Personal"),
        )
        self.db.flush()
        master_tasks = (
            self.master_task(shared.workspace, categories[0], "Tender cama"),
            self.master_task(shared.workspace, categories[2], "Comprar alimentos"),
            self.master_task(shared.workspace, categories[3], "Salir a correr", active=False),
        )
        activity_masters = (
            self.activity_master(shared.workspace, categories[1], "Trabajo"),
            self.activity_master(shared.workspace, categories[2], "Almuerzo"),
            self.activity_master(shared.workspace, categories[3], "Salir a correr", active=False),
        )
        self.db.flush()
        batches = (
            self.generation_batch(shared.workspace, owner, entity_type=GenerationEntityType.TASK, pattern=GenerationPattern.DAILY, date_from=DEFAULT_TODAY, date_until=DEFAULT_TODAY + timedelta(days=3)),
            self.generation_batch(shared.workspace, owner, entity_type=GenerationEntityType.TASK, pattern=GenerationPattern.WEEKLY, date_from=DEFAULT_TODAY, date_until=DEFAULT_TODAY + timedelta(days=14), weekdays=[0, 2, 4]),
            self.generation_batch(shared.workspace, owner, entity_type=GenerationEntityType.ACTIVITY, pattern=GenerationPattern.MONTHLY, date_from=DEFAULT_TODAY, date_until=date(2026, 5, 31), month_days=[29, 30, 31]),
        )
        self.db.flush()
        tasks = (
            self.task(shared.workspace, master_tasks[0], member_a, owner, DEFAULT_TODAY + timedelta(days=1)),
            self.task(shared.workspace, master_tasks[0], member_b, owner, DEFAULT_TODAY + timedelta(days=1)),
            self.task(shared.workspace, master_tasks[1], member_a, owner, DEFAULT_TODAY),
            self.task(shared.workspace, master_tasks[1], member_b, owner, DEFAULT_TODAY - timedelta(days=1), result=TaskResult.COMPLETED),
            self.task(shared.workspace, master_tasks[2], member_c, owner, DEFAULT_TODAY - timedelta(days=2), result=TaskResult.NOT_COMPLETED),
            self.task(shared.workspace, master_tasks[0], owner, owner, DEFAULT_TODAY + timedelta(days=2), batch=batches[0]),
        )
        pending_items = (
            self.pending_item(shared.workspace, categories[0], member_a, owner, "Preparar documentos", progress=0, planned_date=DEFAULT_TODAY + timedelta(days=7)),
            self.pending_item(shared.workspace, categories[1], member_b, owner, "Seguimiento laboral", progress=60, planned_date=DEFAULT_TODAY + timedelta(days=2)),
            self.pending_item(shared.workspace, categories[0], member_c, owner, "Pendiente atrasado", progress=20, planned_date=DEFAULT_TODAY - timedelta(days=3)),
            self.pending_item(shared.workspace, categories[0], member_a, owner, "Pendiente finalizado", progress=100, planned_date=DEFAULT_TODAY),
            self.pending_item(shared.workspace, categories[0], owner, owner, "Pendiente inactivo", active=False, planned_date=None),
        )
        self.db.flush()
        pending_history = (
            self.pending_history(pending_items[1], member_b, 20, comment="Inicio", recorded_at=DEFAULT_NOW - timedelta(days=2)),
            self.pending_history(pending_items[1], member_b, 60, comment="Avance", recorded_at=DEFAULT_NOW - timedelta(days=1)),
            self.pending_history(pending_items[3], member_a, 100, comment="Finalizado", recorded_at=DEFAULT_NOW),
        )
        projects = (
            self.project(shared.workspace, categories[0], member_a, owner, "Proyecto familiar"),
            self.project(shared.workspace, categories[1], member_b, owner, "Proyecto inactivo", active=False),
        )
        self.db.flush()
        stages = (
            self.project_stage(projects[0], member_a, "Preparación", position=0, weight=Decimal("30.00"), progress=100, planned_date=DEFAULT_TODAY),
            self.project_stage(projects[0], member_b, "Ejecución", position=1, weight=Decimal("40.00"), progress=50, planned_date=DEFAULT_TODAY + timedelta(days=7)),
            self.project_stage(projects[0], member_c, "Cierre", position=2, weight=Decimal("30.00"), progress=0, planned_date=DEFAULT_TODAY + timedelta(days=14)),
        )
        self.db.flush()
        stage_history = (
            self.project_stage_history(stages[0], member_a, 50, comment="Primer avance", recorded_at=DEFAULT_NOW - timedelta(days=2)),
            self.project_stage_history(stages[0], member_a, 100, comment="Etapa completa", recorded_at=DEFAULT_NOW - timedelta(days=1)),
            self.project_stage_history(stages[1], member_b, 50, comment="En curso", recorded_at=DEFAULT_NOW),
        )
        self._add(ProjectLeaderHistory(id=self._id("leader-history"), project_id=projects[0].id, workspace_id=shared.workspace.id, leader_user_id=member_a.id, actor_user_id=owner.id, recorded_at=DEFAULT_NOW))
        self.db.flush()

        activities = (
            self.activity(shared.workspace, owner, "Trabajo planificado", starts_at=DEFAULT_NOW + timedelta(days=1), activity_master=activity_masters[0]),
            self.activity(shared.workspace, member_a, "Otra actividad", starts_at=DEFAULT_NOW + timedelta(days=2), custom_category=categories[0]),
            self.activity(shared.workspace, owner, "Actividad recurrente", starts_at=DEFAULT_NOW + timedelta(days=30), activity_master=activity_masters[1], batch=batches[2]),
            self.activity(personal_a.workspace, personal_a.user, "Actividad personal", starts_at=DEFAULT_NOW + timedelta(hours=2), custom_category=categories[4]),
        )
        self.db.flush()
        participants = (
            self.participant(activities[0], member_a),
            self.participant(activities[0], member_b),
            self.participant(activities[0], member_c, removed=True),
        )
        activity_reminders = (
            self.activity_reminder(activities[0], owner),
            self.activity_reminder(activities[0], member_a),
            self.activity_reminder(activities[0], member_c, enabled=False),
        )
        self.db.flush()
        review_metadata = (self.review_metadata(owner, offset=1), self.review_metadata(member_a, offset=3))
        preferences = (
            self.reminder_preference(owner, ReminderType.DAILY_SUMMARY, local_time=time(7), schedule_kind=ScheduleKind.DAILY),
            self.reminder_preference(owner, ReminderType.DAILY_REVIEW, local_time=time(21), schedule_kind=ScheduleKind.DAILY),
            self.reminder_preference(owner, ReminderType.PENDING_FOLLOW_UP, local_time=time(9), schedule_kind=ScheduleKind.WEEKLY, weekdays=[0]),
            self.reminder_preference(owner, ReminderType.PROJECT_FOLLOW_UP, local_time=time(10), schedule_kind=ScheduleKind.MONTHLY, month_days=[1]),
            self.reminder_preference(member_a, ReminderType.DAILY_SUMMARY, local_time=time(8), schedule_kind=ScheduleKind.DAILY),
        )
        notifications = (
            self.notification(member_a, NotificationType.TASK_ASSIGNED, workspace=shared.workspace, actor=owner, label="task-assigned"),
            self.notification(member_b, NotificationType.WORKSPACE_INVITATION, workspace=shared.workspace, actor=owner, read=True, label="invitation"),
            self.notification(owner, NotificationType.ACTIVITY_UPDATED, workspace=shared.workspace, actor=member_a, label="activity-update"),
            self.notification(member_a, NotificationType.ACTIVITY_CANCELLED, workspace=shared.workspace, actor=owner, label="activity-cancelled"),
            self.notification(owner, NotificationType.DAILY_SUMMARY_REMINDER, workspace=None, label="daily-summary"),
            self.notification(owner, NotificationType.DAILY_REVIEW_REMINDER, workspace=None, label="daily-review"),
            self.notification(member_a, NotificationType.PENDING_FOLLOW_UP_REMINDER, workspace=shared.workspace, label="pending-follow-up"),
            self.notification(member_b, NotificationType.PROJECT_FOLLOW_UP_REMINDER, workspace=shared.workspace, label="project-follow-up"),
            self.notification(member_c, NotificationType.ACTIVITY_REMINDER, workspace=shared.workspace, label="activity-reminder"),
        )
        subscriptions = (
            self.push_subscription(owner, label="active"),
            self.push_subscription(member_a, active=False, label="invalid"),
        )
        self.db.flush()
        deliveries = (
            self.delivery(notifications[5], subscriptions[0], DeliveryStatus.PENDING),
            self.delivery(notifications[2], subscriptions[0], DeliveryStatus.DELIVERED),
            self.delivery(notifications[4], subscriptions[1], DeliveryStatus.FAILED),
        )
        self.invitation(shared.workspace, owner, status=InvitationStatus.PENDING)
        self.invitation(shared.workspace, owner, status=InvitationStatus.ACCEPTED, recipient=member_a)

        self.db.flush()
        return CanonicalV2Dataset(
            users=(personal_a.user, personal_b.user, personal_c.user, member_d),
            personal_workspaces=(personal_a, personal_b, personal_c), shared_workspace=shared,
            categories=categories, master_tasks=master_tasks, activity_masters=activity_masters,
            generation_batches=batches, tasks=tasks, pending_items=pending_items,
            pending_history=pending_history, projects=projects, project_stages=stages,
            project_stage_history=stage_history, activities=activities, participants=participants,
            activity_reminders=activity_reminders, review_metadata=review_metadata,
            reminder_preferences=preferences, notifications=notifications,
            push_subscriptions=subscriptions, deliveries=deliveries,
        )
