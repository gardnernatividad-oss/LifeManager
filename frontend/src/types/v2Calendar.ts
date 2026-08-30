export interface CalendarPerson {
  user_id: string;
  display_name: string;
  email: string;
}

export interface CalendarActivity {
  activity_id: string;
  workspace: {
    id: string;
    name: string;
    kind: "PERSONAL" | "SHARED";
    color: "GREEN" | "BLUE" | "PURPLE" | "ORANGE" | "RED" | "TEAL";
    icon: "HOME" | "USERS" | "HEART" | "STAR" | "CALENDAR" | "BRIEFCASE";
  };
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

export interface CalendarUntimed {
  id: string;
  workspace: CalendarActivity["workspace"];
  name: string;
  planned_date: string;
}

export interface CalendarDayCounts {
  date: string;
  activities: number;
  tasks: number;
  pending_items: number;
  project_stages: number;
}

export interface MyCalendarResponse {
  items: CalendarActivity[];
  tasks?: CalendarUntimed[];
  pending_items?: CalendarUntimed[];
  project_stages?: CalendarUntimed[];
  daily_counts?: CalendarDayCounts[];
}
