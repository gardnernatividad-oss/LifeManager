export interface DashboardSummary {
  pending_tasks: number;
  scheduled_tasks: number;
  completed_tasks: number;
  not_completed_tasks: number;
  cancelled_tasks: number;
  total_tasks: number;
  tasks_due_today: number;
  tasks_due_next_7_days: number;
  overdue_tasks: number;
}

export interface DashboardStatistics {
  completion_rate: number;
  completed_tasks: number;
  not_completed_tasks: number;
  cancelled_tasks: number;
  resolved_tasks: number;
  pending_tasks: number;
  scheduled_tasks: number;
}
