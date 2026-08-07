export const queryKeys = {
  workspaces: ["workspaces"] as const,
  dashboardSummary: (workspaceId: string) => ["dashboard", "summary", workspaceId] as const,
  dashboardStatistics: (workspaceId: string) => ["dashboard", "statistics", workspaceId] as const,
  categories: (workspaceId: string, active: boolean | null) =>
    ["categories", workspaceId, active] as const,
  categoriesForWorkspace: (workspaceId: string) => ["categories", workspaceId] as const
};
