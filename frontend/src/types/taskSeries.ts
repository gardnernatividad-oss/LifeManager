export type TaskSeriesFrequency = "daily" | "weekly" | "monthly";

export interface TaskSeries {
  id: string;
  workspace_id: string;
  created_by_id: string;
  category_id: string | null;
  project_id: string | null;
  title: string;
  description: string | null;
  timezone: string;
  frequency: TaskSeriesFrequency;
  interval: number;
  weekdays: number[] | null;
  month_day: number | null;
  starts_at: string;
  ends_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskSeriesWrite {
  title: string;
  description: string | null;
  timezone: string;
  frequency: TaskSeriesFrequency;
  interval: number;
  weekdays: number[] | null;
  month_day: number | null;
  starts_at: string;
  ends_at: string | null;
  category_id: string | null;
  project_id: string | null;
}

export interface TaskSeriesListResponse { items: TaskSeries[]; total: number; }
export interface TaskSeriesWindow { window_start: string; window_end: string; }
export interface MaterializationResponse { generated_count: number; generated_task_ids: string[]; }
export interface SynchronizationResponse {
  created_count: number; updated_count: number; deleted_count: number;
  created_task_ids: string[]; updated_task_ids: string[]; deleted_task_ids: string[];
}
