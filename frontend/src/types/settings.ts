export type WeekStartsOn = "MONDAY" | "SUNDAY";

export interface UserSettings {
  id: string;
  user_id: string;
  timezone: string;
  locale: string;
  week_starts_on: WeekStartsOn;
  daily_form_reminders_enabled: boolean;
  task_due_reminders_enabled: boolean;
  task_overdue_reminders_enabled: boolean;
  daily_form_reminder_time: string;
  task_due_reminder_minutes: number;
  created_at: string;
  updated_at: string;
}

export type UserSettingsWrite = Omit<UserSettings, "id" | "user_id" | "created_at" | "updated_at">;

export interface WorkspaceSettings {
  id: string;
  workspace_id: string;
  timezone: string;
  daily_form_enabled: boolean;
  daily_form_reminder_time: string;
  daily_task_generation_enabled: boolean;
  week_starts_on: WeekStartsOn;
  created_at: string;
  updated_at: string;
}

export type WorkspaceSettingsWrite = Omit<WorkspaceSettings, "id" | "workspace_id" | "created_at" | "updated_at">;
