export type ActivityTemporalState = "FUTURE" | "IN_PROGRESS" | "PAST";
export type ActivityMutationScope = "THIS" | "THIS_AND_FUTURE";

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
  is_custom?: boolean;
  custom_category_id?: string | null;
  category_id: string;
  category_name: string;
  title: string;
  organizer_user_id: string;
  organizer_display_name: string;
  organizer_email: string;
  participants: V2ActivityParticipant[];
  reminder_minutes_before: number | null;
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
  custom?: boolean;
}

export type V2ActivitySourceWrite = { activity_master_id: string; custom_name?: never; custom_category_id?: never } | { activity_master_id?: never; custom_name: string; custom_category_id: string };

export type V2ActivityCreate = V2ActivitySourceWrite & {
  organizer_user_id?: string;
  participant_user_ids: string[];
  starts_at: string;
  ends_at: string;
  reminder_minutes_before?: number | null;
};

export type V2ActivityUpdate = Partial<V2ActivitySourceWrite & {
  organizer_user_id: string;
  participant_user_ids: string[];
  starts_at: string;
  ends_at: string;
  reminder_minutes_before: number | null;
}> & { lock_version: number; scope?: ActivityMutationScope };

export type ActivityRecurrencePattern = "DAILY" | "WEEKLY" | "MONTHLY";

export type V2RecurringActivityCreate = V2ActivitySourceWrite & {
  organizer_user_id?: string;
  participant_user_ids: string[];
  start_time: string;
  end_time: string;
  reminder_minutes_before?: number | null;
  timezone: string;
  recurrence: {
    pattern: ActivityRecurrencePattern;
    date_from: string;
    date_until: string;
    weekdays?: number[];
    month_days?: number[];
  };
};

export interface V2RecurringActivityCreateResponse {
  created_count: number;
  items: V2Activity[];
}
