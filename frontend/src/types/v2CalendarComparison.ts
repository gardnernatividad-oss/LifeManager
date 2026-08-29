export type CalendarVisibility = "SHOW_DETAILS" | "AVAILABILITY_ONLY" | "HIDE";

export interface CalendarComparisonDetail {
  activity_name: string;
  starts_at: string;
  ends_at: string;
  temporal_state: "FUTURE" | "IN_PROGRESS" | "PAST";
}

export interface CalendarBusyBlock {
  starts_at: string;
  ends_at: string;
  occupied: true;
}

export type CalendarComparison =
  | { visibility: "SHOW_DETAILS"; detailed_events: CalendarComparisonDetail[] }
  | { visibility: "AVAILABILITY_ONLY"; busy_blocks: CalendarBusyBlock[] }
  | { visibility: "HIDE" };

export interface CalendarComparisonMember {
  user_id: string;
  display_name: string;
  calendar: CalendarComparison;
}

export interface CalendarComparisonMulti { members: CalendarComparisonMember[] }

export interface CalendarVisibilitySetting {
  visibility: CalendarVisibility;
  lock_version: number;
}
