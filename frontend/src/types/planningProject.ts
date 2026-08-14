export interface PlanningProjectStep {
  id: string; name: string; planned_date: string | null; weight: string | null;
  progress: number; state: string; completion_date: string | null; compliance: string | null;
  detail_days: number | null; comment: string | null; position: number; lock_version: number;
  created_at: string; updated_at: string;
}
export interface PlanningProject {
  id: string; category_id: string; category: { id: string; name: string }; name: string;
  is_active: boolean; planned_date: string | null; progress: string | null; state: string | null;
  total_weight: string; general_comment: string | null; last_tracking_saved_at: string | null;
  lock_version: number; created_at: string; updated_at: string;
}
export interface PlanningProjectDetail extends PlanningProject { steps: PlanningProjectStep[] }
export type ProjectState = "NO_INICIADO" | "EN_PROCESO" | "FINALIZADO";
export type StepCompliance = "EN_PLAZO" | "ATRASADO" | "CON_ADELANTO" | "A_TIEMPO" | "CON_RETRASO";
export interface PlanningProjectListParams { page: number; page_size: number; is_active?: boolean; category_id?: string; state?: ProjectState; planned_from?: string; planned_to?: string }
export interface PlanningProjectListResponse { items: PlanningProject[]; total: number; page: number; page_size: number; total_pages: number }
export interface PlanningStepInput { name: string; planned_date: string | null; weight: string | null; position: number }
export interface PlanningProjectCreatePayload { category_id: string; name: string; is_active: boolean; steps: PlanningStepInput[] }
export interface PlanningProjectUpdatePayload { category_id?: string; name?: string; is_active?: boolean; lock_version: number }
export interface PlanningStepUpdatePayload { name?: string; planned_date?: string | null; weight?: string | null; position?: number; lock_version: number }
export interface ProjectStepTrackingUpdate { id: string; progress?: number; comment?: string | null; lock_version: number }
export interface ProjectTrackingBatchResponse { project: PlanningProjectDetail; saved_at: string }
