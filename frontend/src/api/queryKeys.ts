export const queryKeys = {
  workspaces: ["workspaces"] as const,
  dashboardSummary: (workspaceId: string) => ["dashboard", "summary", workspaceId] as const,
  dashboardStatistics: (workspaceId: string) => ["dashboard", "statistics", workspaceId] as const,
  categories: (workspaceId: string, active: boolean | null) =>
    ["categories", workspaceId, active] as const,
  categoriesForWorkspace: (workspaceId: string) => ["categories", workspaceId] as const,
  projects: (workspaceId: string, active: boolean | null) =>
    ["projects", workspaceId, active] as const,
  projectsForWorkspace: (workspaceId: string) => ["projects", workspaceId] as const,
  tasks: (workspaceId: string, filters: object) => ["tasks", workspaceId, filters] as const,
  tasksForWorkspace: (workspaceId: string) => ["tasks", workspaceId] as const,
  taskSeries: (workspaceId: string, active: boolean | null) => ["task-series", workspaceId, active] as const,
  taskSeriesForWorkspace: (workspaceId: string) => ["task-series", workspaceId] as const
};
