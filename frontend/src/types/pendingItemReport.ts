export type PendingItemState = "NO_INICIADO" | "EN_PROCESO" | "FINALIZADO";
export type PendingItemCompliance =
  | "EN_PLAZO"
  | "ATRASADO"
  | "CON_ADELANTO"
  | "A_TIEMPO"
  | "CON_RETRASO";

export interface PendingItemReportParams {
  planned_from?: string;
  planned_to?: string;
  category_id?: string;
  is_active?: boolean;
  state?: PendingItemState;
  compliance?: PendingItemCompliance;
}

export interface PendingItemReportSummary {
  total_count: number;
  active_count: number;
  inactive_count: number;
  no_iniciado_count: number;
  en_proceso_count: number;
  finalizado_count: number;
}

export interface PendingItemComplianceSummary {
  en_plazo_count: number;
  atrasado_count: number;
  con_adelanto_count: number;
  a_tiempo_count: number;
  con_retraso_count: number;
}

export interface PendingItemDetailSummary {
  average_atrasado_days: string | number | null;
  average_con_adelanto_days: string | number | null;
  average_con_retraso_days: string | number | null;
}

export interface PendingItemCategoryReportRow {
  category_id: string;
  category_name: string;
  summary: PendingItemReportSummary;
  compliance: PendingItemComplianceSummary;
}

export interface PendingItemReportResponse {
  period: { planned_from: string | null; planned_to: string | null };
  filters: {
    category_id: string | null;
    is_active: boolean | null;
    state: PendingItemState | null;
    compliance: PendingItemCompliance | null;
  };
  summary: PendingItemReportSummary;
  compliance: PendingItemComplianceSummary;
  detail: PendingItemDetailSummary;
  by_category: PendingItemCategoryReportRow[];
}
