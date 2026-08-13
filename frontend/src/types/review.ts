export type ReviewTaskResult = "COMPLETED" | "NOT_COMPLETED";

export interface ReviewTask {
  id: string;
  planned_date: string;
  name: string;
  lock_version: number;
}

export interface ReviewEditableRow {
  id: string;
  planned_date: string;
  name: string;
  progress: number;
  comment: string | null;
  lock_version: number;
}

export interface ReviewProjectStep extends ReviewEditableRow {
  weight: string;
}

export interface ReviewProjectGroup {
  id: string;
  name: string;
  steps: ReviewProjectStep[];
}

export interface ReviewRead {
  review_date: string;
  last_review_saved_at: string | null;
  tasks: ReviewTask[];
  pending_items: ReviewEditableRow[];
  projects: ReviewProjectGroup[];
}

export interface ReviewSave {
  tasks: Array<{ id: string; result: ReviewTaskResult; lock_version: number }>;
  pending_items: Array<{ id: string; progress?: number; comment?: string | null; lock_version: number }>;
  project_steps: Array<{ id: string; progress?: number; comment?: string | null; lock_version: number }>;
}

export interface ReviewSaveResponse {
  saved_at: string;
}
