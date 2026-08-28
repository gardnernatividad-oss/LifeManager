export interface CalendarPerson {
  user_id: string;
  display_name: string;
  email: string;
}

export interface CalendarActivity {
  activity_id: string;
  workspace: { id: string; name: string; kind: "PERSONAL" | "SHARED" };
  activity_name: string;
  category_name: string;
  starts_at: string;
  ends_at: string;
  organizer: CalendarPerson;
  participants: CalendarPerson[];
  status: "SCHEDULED" | "CANCELLED";
  temporal_state: "FUTURE" | "IN_PROGRESS" | "PAST";
  lock_version: number;
  can_edit: boolean;
  can_delete: boolean;
  can_leave_participation: boolean;
}

export interface MyCalendarResponse { items: CalendarActivity[] }
