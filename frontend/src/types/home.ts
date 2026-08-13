export interface HomeSummary {
  user_first_name: string;
  local_date: string;
  tasks: {
    due_today: number;
    overdue: number;
  };
  pending_items: {
    overdue: number;
  };
  project_steps: {
    overdue: number;
  };
  last_review_saved_at: string | null;
  pending_items_last_tracking_saved_at: string | null;
}
