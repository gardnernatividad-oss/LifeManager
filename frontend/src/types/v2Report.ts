export interface V2ReportFilters {
  date_from?: string;
  date_until?: string;
  category_id?: string;
  responsible_user_id?: string;
}

export interface V2ReportSummary {
  local_date: string;
  date_from: string | null;
  date_until: string | null;
  category_id: string | null;
  responsible_user_id: string | null;
  counts: {
    tasks: number;
    pending_items: number;
    projects: number;
    activities: number;
    total: number;
  };
}

export interface TaskReportMetrics { total_count: number; pending_count: number; completed_count: number; not_completed_count: number; resolved_count: number; completion_rate: string | null }
export interface TaskReportGroup extends TaskReportMetrics { key: string; label: string }
export interface TaskReportEvolution extends TaskReportMetrics { planned_date: string }
export interface V2TaskReport { period: { date_from: string | null; date_until: string | null }; filters: V2ReportFilters; master_task_id: string | null; custom_tasks: boolean | null; summary: TaskReportMetrics; by_task: TaskReportGroup[]; by_category: TaskReportGroup[]; evolution: TaskReportEvolution[] }
export interface ProgressReportMetrics { total_count: number; no_iniciado_count: number; en_proceso_count: number; finalizado_count: number; configuracion_incompleta_count?: number; average_progress: string | null }
export interface ComplianceMetrics { en_plazo_count: number; atrasado_count: number; con_adelanto_count: number; a_tiempo_count: number; con_retraso_count: number }
export interface ProgressCategoryGroup extends ProgressReportMetrics { category_id: string; category_name: string }
export interface ProgressEvolution { planned_date: string; total_count: number; average_progress: string | null }
export interface V2PendingReport { period: { date_from: string | null; date_until: string | null }; filters: V2ReportFilters; summary: ProgressReportMetrics; compliance: ComplianceMetrics; by_category: ProgressCategoryGroup[]; evolution: ProgressEvolution[] }
export interface ProjectReportRow { project_id: string; project_name: string; category_id: string; category_name: string; planned_date: string | null; progress: string | null; state: string; stage_count: number }
export interface V2ProjectReport { period: { date_from: string | null; date_until: string | null }; filters: V2ReportFilters; summary: ProgressReportMetrics; stage_compliance: ComplianceMetrics; by_category: ProgressCategoryGroup[]; by_project: ProjectReportRow[]; evolution: ProgressEvolution[] }
export interface ActivityReportMetrics { total_count: number; scheduled_count: number; cancelled_count: number; total_duration_minutes: string; average_duration_minutes: string | null }
export interface ActivityReportGroup extends ActivityReportMetrics { key: string; label: string }
export interface ActivityReportEvolution extends ActivityReportMetrics { local_date: string }
export interface V2ActivityReport { period: { date_from: string | null; date_until: string | null }; filters: V2ReportFilters; activity_master_id: string | null; custom_activities: boolean | null; summary: ActivityReportMetrics; by_activity: ActivityReportGroup[]; by_category: ActivityReportGroup[]; by_organizer: ActivityReportGroup[]; evolution: ActivityReportEvolution[] }
