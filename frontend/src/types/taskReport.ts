export interface TaskReportParams { planned_from?: string; planned_to?: string; master_task_id?: string; category_id?: string }
export interface TaskOutcomeMetrics { completed_count:number; not_completed_count:number; terminal_count:number; completion_rate:string|number|null }
export interface TaskReportRow extends TaskOutcomeMetrics { master_task_id:string; master_task_name:string; category_id:string; category_name:string }
export interface TaskReportResponse { period:{planned_from:string|null;planned_to:string|null}; summary:TaskOutcomeMetrics; by_master_task:TaskReportRow[] }
