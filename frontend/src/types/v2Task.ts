export type V2TaskState = "PROGRAMADA" | "PENDIENTE" | "COMPLETADA" | "NO_REALIZADA";
export type V2TaskResult = "COMPLETED" | "NOT_COMPLETED";
export type V2TaskMutationScope = "THIS" | "THIS_AND_FUTURE";

export interface V2Task {
  id: string; workspace_id: string; source?: "CATALOG" | "CUSTOM";
  master_task_id: string | null; master_task_name: string | null;
  custom_name?: string | null; custom_category_id?: string | null; task_name?: string;
  category_id: string; category_name: string; responsible_user_id: string;
  responsible_display_name: string; responsible_email: string; planned_date: string;
  state: V2TaskState; result: V2TaskResult | null; resolved_at: string | null;
  resolved_by_user_id: string | null; lock_version: number; is_generated: boolean;
  can_edit_this: boolean; can_edit_future: boolean; can_delete_this: boolean;
  can_delete_future: boolean; can_edit: boolean;
  can_resolve: boolean; can_delete: boolean; created_at: string; updated_at: string;
  can_correct_result?: boolean;
}
export interface V2TaskList { items: V2Task[]; total: number; page: number; page_size: number; total_pages: number; }
export interface V2TaskFilters { page: number; page_size: number; planned_from?: string; planned_until?: string; responsible_user_id?: string; master_task_id?: string; category_id?: string; result?: V2TaskResult; unresolved?: boolean; state?: V2TaskState; generated?: boolean; custom?: boolean; }
export type V2TaskSourceWrite = { master_task_id: string; custom_name?: never; custom_category_id?: never } | { master_task_id?: never; custom_name: string; custom_category_id: string };
export type V2TaskCreate = V2TaskSourceWrite & { planned_date: string; responsible_user_id?: string };
export type V2TaskUpdate = Partial<V2TaskSourceWrite & { planned_date: string; responsible_user_id: string }> & { lock_version: number; scope?: V2TaskMutationScope; };
export type V2TaskRecurrencePattern = "DAILY" | "WEEKLY" | "MONTHLY";
export interface V2TaskRecurrence { pattern: V2TaskRecurrencePattern; date_from: string; date_until: string; weekdays?: number[]; month_days?: number[]; }
export type V2RecurringTaskCreate = V2TaskSourceWrite & { responsible_user_id?: string; recurrence: V2TaskRecurrence };
export interface V2RecurringTaskCreateResponse { created_count: number; items: V2Task[]; }
