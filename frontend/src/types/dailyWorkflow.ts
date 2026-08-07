export type DailyWorkflowStatus = "READY" | "ACTION_REQUIRED";

export interface DailyTaskGeneration {
  workspace_id: string;
  generation_date: string;
  eligible_series_count: number;
  created_task_count: number;
  skipped_existing_count: number;
  created_task_ids: string[];
  generated_at: string;
}

export interface DailyWorkflow {
  workspace_id: string;
  user_id: string;
  workflow_date: string;
  workflow_status: DailyWorkflowStatus;
  form_required: boolean;
  form_submitted: boolean;
  definition_id: string | null;
  submission_id: string | null;
  task_generation: DailyTaskGeneration;
  evaluated_at: string;
}

export interface WorkspaceSettings {
  id: string;
  workspace_id: string;
  timezone: string;
  daily_form_enabled: boolean;
  daily_form_reminder_time: string;
  daily_task_generation_enabled: boolean;
  week_starts_on: string;
  created_at: string;
  updated_at: string;
}
