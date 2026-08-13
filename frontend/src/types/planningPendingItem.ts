export interface CategoryOption { id: string; name: string; created_at: string; updated_at: string }
export interface CategoryOptionPage { items: CategoryOption[]; total: number; page: number; page_size: number; total_pages: number }
export interface PlanningPendingItem {
  id: string; category_id: string; category: { id: string; name: string }; name: string;
  is_active: boolean; planned_date: string | null; progress: number; state: string;
  completion_date: string | null; compliance: string | null; detail_days: number | null;
  comment: string | null; lock_version: number; created_at: string; updated_at: string;
}
export interface PendingItemListParams { page: number; page_size: number; is_active?: boolean; category_id?: string; planned_from?: string; planned_to?: string }
export interface PendingItemListResponse { items: PlanningPendingItem[]; total: number; page: number; page_size: number; total_pages: number }
export interface PendingItemCreatePayload { category_id: string; name: string; is_active: boolean; planned_date: string | null }
export interface PendingItemUpdatePayload { category_id?: string; name?: string; is_active?: boolean; planned_date?: string | null; lock_version: number }
