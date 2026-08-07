export type ReportPeriod = "this_week" | "this_month" | "last_30_days" | "custom";

export interface ReportPeriodBounds {
  scheduledFrom: string;
  scheduledTo: string;
  fromDate: string;
  toDate: string;
}

export interface ReportTaskCounts {
  total: number;
  completed: number;
  notCompleted: number;
  cancelled: number;
  unresolved: number;
}
