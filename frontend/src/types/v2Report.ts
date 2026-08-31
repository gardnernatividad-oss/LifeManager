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
