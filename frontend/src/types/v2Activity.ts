export type ActivityTemporalState = "FUTURE" | "IN_PROGRESS" | "PAST";

export interface V2ActivityParticipant {
  user_id: string;
  display_name: string;
  email: string;
  calendar_status: "VISIBLE" | "REMOVED";
}

export interface V2Activity {
  id: string;
  workspace_id: string;
  activity_master_id: string | null;
  activity_master_name: string | null;
  category_id: string;
  category_name: string;
  title: string;
  organizer_user_id: string;
  organizer_display_name: string;
  organizer_email: string;
  participants: V2ActivityParticipant[];
  starts_at: string;
  ends_at: string;
  status: "SCHEDULED" | "CANCELLED";
  temporal_state: ActivityTemporalState;
  lock_version: number;
  is_generated: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_leave_participation: boolean;
  created_at: string;
  updated_at: string;
}

export interface V2ActivityList {
  items: V2Activity[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface V2ActivityFilters {
  page: number;
  page_size: number;
  starts_from?: string;
  starts_until?: string;
  activity_master_id?: string;
  category_id?: string;
  organizer_user_id?: string;
  participant_user_id?: string;
}

export interface V2ActivityCreate {
  activity_master_id: string;
  organizer_user_id?: string;
  participant_user_ids: string[];
  starts_at: string;
  ends_at: string;
}

export interface V2ActivityUpdate extends Partial<V2ActivityCreate> {
  lock_version: number;
}
