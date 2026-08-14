export type ProjectReportState = "NO_INICIADO" | "EN_PROCESO" | "FINALIZADO";

export interface ProjectReportParams {
  planned_from?: string;
  planned_to?: string;
  category_id?: string;
  is_active?: boolean;
  state?: ProjectReportState;
}

export interface ProjectReportSummary {
  total_count: number;
  active_count: number;
  inactive_count: number;
  no_iniciado_count: number;
  en_proceso_count: number;
  finalizado_count: number;
}

export interface ProjectStepComplianceSummary {
  en_plazo_count: number;
  atrasado_count: number;
  con_adelanto_count: number;
  a_tiempo_count: number;
  con_retraso_count: number;
}

export interface ProjectStepDetailSummary {
  average_atrasado_days: string | number | null;
  average_con_adelanto_days: string | number | null;
  average_con_retraso_days: string | number | null;
}

export interface ProjectReportRow {
  project_id: string;
  project_name: string;
  category_id: string;
  category_name: string;
  is_active: boolean;
  planned_date: string | null;
  progress: string | number | null;
  state: ProjectReportState | null;
  step_count: number;
}

export interface ProjectReportResponse {
  period: { planned_from: string | null; planned_to: string | null };
  filters: {
    category_id: string | null;
    is_active: boolean | null;
    state: ProjectReportState | null;
  };
  summary: ProjectReportSummary;
  step_compliance: ProjectStepComplianceSummary;
  detail: ProjectStepDetailSummary;
  by_project: ProjectReportRow[];
}
