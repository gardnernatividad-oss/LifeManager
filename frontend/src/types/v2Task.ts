export type V2TaskState = "PROGRAMADA" | "PENDIENTE" | "COMPLETADA" | "NO_REALIZADA";
export type V2TaskResult = "COMPLETED" | "NOT_COMPLETED";

export interface V2Task {
  id: string; workspace_id: string; master_task_id: string; master_task_name: string;
  category_id: string; category_name: string; responsible_user_id: string;
  responsible_display_name: string; responsible_email: string; planned_date: string;
  state: V2TaskState; result: V2TaskResult | null; resolved_at: string | null;
  resolved_by_user_id: string | null; lock_version: number; can_edit: boolean;
  can_resolve: boolean; can_delete: boolean; created_at: string; updated_at: string;
}
export interface V2TaskList { items: V2Task[]; total: number; page: number; page_size: number; total_pages: number; }
export interface V2TaskFilters { page: number; page_size: number; planned_from?: string; planned_until?: string; responsible_user_id?: string; master_task_id?: string; category_id?: string; result?: V2TaskResult; unresolved?: boolean; }
export interface V2TaskCreate { master_task_id: string; planned_date: string; responsible_user_id?: string; }
export interface V2TaskUpdate { master_task_id?: string; planned_date?: string; responsible_user_id?: string; lock_version: number; }
