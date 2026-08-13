export type PlanningTaskStatus = "PROGRAMADA" | "PENDIENTE" | "COMPLETADA" | "NO_REALIZADA";
export type BulkTaskPattern = "DAILY" | "WEEKLY";

export interface MasterTaskOption {
  id: string;
  name: string;
  category_id: string;
  category: { id: string; name: string };
  created_at: string;
  updated_at: string;
}

export interface MasterTaskListResponse {
  items: MasterTaskOption[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PlanningTask {
  id: string;
  master_task_id: string;
  planned_date: string;
  status: PlanningTaskStatus;
  result: "COMPLETED" | "NOT_COMPLETED" | null;
  resolved_at: string | null;
  resolved_by_id: string | null;
  master_task: Pick<MasterTaskOption, "id" | "name" | "category_id" | "category">;
  lock_version: number;
  created_at: string;
  updated_at: string;
}

export interface PlanningTaskListParams {
  page: number;
  page_size: number;
  planned_from?: string;
  planned_to?: string;
  master_task_id?: string;
  category_id?: string;
  status?: PlanningTaskStatus;
}

export interface PlanningTaskListResponse {
  items: PlanningTask[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TaskCreatePayload { master_task_id: string; planned_date: string }
export interface TaskBulkCreatePayload {
  master_task_id: string;
  start_date: string;
  end_date: string;
  pattern: BulkTaskPattern;
  weekdays?: number[];
}
export interface TaskBulkCreateResponse { created_count: number; items: PlanningTask[] }
export interface TaskUpdatePayload { planned_date: string; lock_version: number }
export interface TaskDeleteItem { id: string; lock_version: number }
