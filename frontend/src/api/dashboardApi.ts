import { apiClient } from "./client";
import type { DashboardStatistics, DashboardSummary } from "../types/dashboard";

export async function getDashboardSummary(workspaceId: string): Promise<DashboardSummary> {
  const response = await apiClient.get<DashboardSummary>(
    `/workspaces/${workspaceId}/dashboard`
  );
  return response.data;
}

export async function getDashboardStatistics(workspaceId: string): Promise<DashboardStatistics> {
  const response = await apiClient.get<DashboardStatistics>(
    `/workspaces/${workspaceId}/dashboard/statistics`
  );
  return response.data;
}
