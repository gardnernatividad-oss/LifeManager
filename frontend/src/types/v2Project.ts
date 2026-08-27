export interface V2Project {
  id: string; workspace_id: string; category_id: string; category_name: string;
  leader_user_id: string; leader_display_name: string; leader_email: string;
  name: string; description: string | null; is_active: boolean;
  planned_date: string | null; progress: number | null; state: string | null;
  compliance: string | null; compliance_detail_days: number | null; completion_date: string | null;
  weights_complete: boolean; stage_count: number; total_weight: string;
  lock_version: number; can_edit: boolean; can_deactivate: boolean; can_reactivate: boolean;
  created_at: string; updated_at: string;
}
export interface V2ProjectList { items: V2Project[]; total: number; page: number; page_size: number; total_pages: number; }
export interface V2ProjectFilters { page: number; page_size: number; is_active?: boolean; category_id?: string; leader_user_id?: string; search?: string; }
export interface V2ProjectCreate { category_id: string; leader_user_id?: string; name: string; description?: string | null; }
export interface V2ProjectUpdate { category_id?: string; leader_user_id?: string; name?: string; description?: string | null; lock_version: number; }
