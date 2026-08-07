export type TaskStatus = "scheduled" | "pending" | "completed" | "not_completed" | "cancelled";
export type TaskOutcome = "completed" | "not_completed" | "cancelled";
export type TaskOrderBy = "scheduled_at" | "created_at" | "updated_at" | "title";
export type OrderDirection = "asc" | "desc";

export interface Task {
  id: string;
  workspace_id: string;
  created_by_id: string;
  category_id: string | null;
  project_id: string | null;
  task_series_id: string | null;
  title: string;
  description: string | null;
  scheduled_at: string;
  status: TaskStatus;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskWrite {
  title: string;
  description: string | null;
  scheduled_at: string;
  category_id: string | null;
  project_id: string | null;
}

export type TaskUpdate = Partial<TaskWrite>;

export interface TaskListParams {
  page: number;
  pageSize: number;
  search: string;
  status: TaskStatus | "";
  outcome: TaskOutcome | "";
  categoryId: string;
  projectId: string;
  scheduledFrom: string;
  scheduledTo: string;
  orderBy: TaskOrderBy;
  orderDirection: OrderDirection;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
