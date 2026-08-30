export type ReviewTaskResult = "COMPLETED" | "NOT_COMPLETED";

interface ReviewItem {
  id: string;
  workspace_id: string;
  workspace_name: string;
  planned_date: string;
  lock_version: number;
}

export interface ReviewTask extends ReviewItem {
  task_name: string;
}

export interface ReviewPendingItem extends ReviewItem {
  pending_item_name: string;
  progress: number;
}

export interface ReviewProjectStage extends ReviewItem {
  project_id: string;
  project_name: string;
  stage_name: string;
  progress: string;
  project_lock_version: number;
}

export interface ReviewRead {
  review_date: string;
  tasks: ReviewTask[];
  pending_items: ReviewPendingItem[];
  project_stages: ReviewProjectStage[];
}

export interface ReviewTaskBatch {
  items: Array<{ task_id: string; result: ReviewTaskResult; lock_version: number }>;
}

export interface ReviewPendingBatch {
  items: Array<{ pending_item_id: string; progress?: number; comment?: string; lock_version: number }>;
}

export interface ReviewProjectStageBatch {
  items: Array<{ stage_id: string; progress?: string; comment?: string; lock_version: number; project_lock_version: number }>;
}

export interface ReviewBlockSaveResponse {
  saved_ids: string[];
}
