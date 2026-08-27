export type V2PendingItemState = "NO_INICIADO" | "EN_PROCESO" | "FINALIZADO";
export type V2PendingItemCompliance = "EN_PLAZO" | "ATRASADO" | "A_TIEMPO" | "CON_ADELANTO" | "CON_RETRASO";

export interface V2PendingItem {
  id: string; workspace_id: string; category_id: string; category_name: string;
  responsible_user_id: string; responsible_display_name: string; responsible_email: string;
  name: string; is_active: boolean; planned_date: string | null; progress: number;
  state: V2PendingItemState; completion_date: string | null;
  compliance: V2PendingItemCompliance | null; compliance_detail_days: number | null;
  lock_version: number; can_edit: boolean; can_update_progress: boolean;
  can_correct: boolean; can_deactivate: boolean; can_reactivate: boolean;
  can_delete: boolean; created_at: string; updated_at: string;
}
export interface V2PendingItemList { items: V2PendingItem[]; total: number; page: number; page_size: number; total_pages: number; }
export interface V2PendingItemCreate { category_id: string; responsible_user_id?: string; name: string; planned_date: string; }
export interface V2PendingItemUpdate { category_id?: string; responsible_user_id?: string; name?: string; planned_date?: string; lock_version: number; }
