import { apiClient } from "./client";
import type { DailyWorkflow, WorkspaceSettings } from "../types/dailyWorkflow";

export async function evaluateDailyWorkflow(workspaceId: string, date: string): Promise<DailyWorkflow> {
  return (await apiClient.post<DailyWorkflow>(`/workspaces/${workspaceId}/daily-workflow/${date}`)).data;
}

export async function getWorkspaceSettings(workspaceId: string): Promise<WorkspaceSettings> {
  return (await apiClient.get<WorkspaceSettings>(`/workspaces/${workspaceId}/settings`)).data;
}
