import { apiClient } from "./client";
import type { WorkspaceSettings, WorkspaceSettingsWrite } from "../types/settings";

export async function getWorkspaceSettings(workspaceId: string): Promise<WorkspaceSettings> {
  return (await apiClient.get<WorkspaceSettings>(`/workspaces/${workspaceId}/settings`)).data;
}

export async function updateWorkspaceSettings(workspaceId: string, payload: WorkspaceSettingsWrite): Promise<WorkspaceSettings> {
  return (await apiClient.put<WorkspaceSettings>(`/workspaces/${workspaceId}/settings`, payload)).data;
}
