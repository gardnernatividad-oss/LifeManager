export type HomeWorkspace = { id: string; name: string; color: string; icon: string };

export type HomeTodayCounts = {
  tasks: number;
  pending_items: number;
  project_stages: number;
  activities: number;
};

export type HomeUpcomingActivity = {
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
  workspace: HomeWorkspace;
};

export type HomeAttentionItem = {
  type: "TASK" | "PENDING_ITEM" | "PROJECT_STAGE";
  id: string;
  name: string;
  planned_date: string;
  workspace: HomeWorkspace;
  project_id: string | null;
};

export type HomeUpcomingDay = HomeTodayCounts & { date: string };

export type V2HomeSummary = {
  local_date: string;
  today: HomeTodayCounts;
  upcoming_activities: HomeUpcomingActivity[];
  attention: HomeAttentionItem[];
  upcoming_days: HomeUpcomingDay[];
};
