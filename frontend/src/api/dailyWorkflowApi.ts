import { apiClient } from "./client";
import type { DailyWorkflow } from "../types/dailyWorkflow";

export async function evaluateDailyWorkflow(workspaceId: string, date: string): Promise<DailyWorkflow> {
  return (await apiClient.post<DailyWorkflow>(`/workspaces/${workspaceId}/daily-workflow/${date}`)).data;
}
