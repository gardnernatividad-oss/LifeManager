export const queryKeys = {
  home: ["home"] as const,
  review: ["review"] as const,
  masterTasks: ["master-tasks", "options"] as const,
  planningTasks: (params: object) => ["tasks", "planning", params] as const,
  planningTasksRoot: ["tasks", "planning"] as const,
  categoryOptions: ["categories", "options"] as const,
  planningPendingItems: (params: object) => ["pending-items", "planning", params] as const,
  planningPendingItemsRoot: ["pending-items", "planning"] as const,
  workspaces: ["workspaces"] as const,
  userSettings: ["user-settings"] as const,
  dashboardSummary: (workspaceId: string) => ["dashboard", "summary", workspaceId] as const,
  dashboardStatistics: (workspaceId: string) => ["dashboard", "statistics", workspaceId] as const,
  reportTaskCounts: (workspaceId: string, scheduledFrom: string, scheduledTo: string) =>
    ["reports", "task-counts", workspaceId, scheduledFrom, scheduledTo] as const,
  categories: (workspaceId: string, active: boolean | null) =>
    ["categories", workspaceId, active] as const,
  categoriesForWorkspace: (workspaceId: string) => ["categories", workspaceId] as const,
  projects: (workspaceId: string, active: boolean | null) =>
    ["projects", workspaceId, active] as const,
  projectsForWorkspace: (workspaceId: string) => ["projects", workspaceId] as const,
  tasks: (workspaceId: string, filters: object) => ["tasks", workspaceId, filters] as const,
  tasksForWorkspace: (workspaceId: string) => ["tasks", workspaceId] as const,
  taskSeries: (workspaceId: string, active: boolean | null) => ["task-series", workspaceId, active] as const,
  taskSeriesForWorkspace: (workspaceId: string) => ["task-series", workspaceId] as const,
  workspaceSettings: (workspaceId: string) => ["workspace-settings", workspaceId] as const,
  dailyWorkflow: (workspaceId: string, date: string) => ["daily-workflow", workspaceId, date] as const,
  dailyFormDefinition: (workspaceId: string) => ["daily-form", "definition", workspaceId] as const,
  dailyFormSubmission: (workspaceId: string, date: string) => ["daily-form", "submission", workspaceId, date] as const
};
