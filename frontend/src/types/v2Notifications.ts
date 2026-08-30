export type ScheduledNotificationPreference = { enabled: boolean; local_time: string; weekday: number | null; lock_version: number };
export type NotificationPreferences = { daily_summary: ScheduledNotificationPreference; daily_review: ScheduledNotificationPreference; pending_weekly: ScheduledNotificationPreference; project_weekly: ScheduledNotificationPreference; activity_reminders: { enabled: boolean; lock_version: number } };
export type PushSubscriptionPayload = { endpoint: string; keys: { p256dh: string; auth: string } };
export type PushSubscriptionRecord = { id: string; is_active: boolean };
