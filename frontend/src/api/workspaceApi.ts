import { apiClient } from "./client";
import type { WorkspaceSummary } from "../types/auth";

export async function listWorkspaces(): Promise<WorkspaceSummary[]> {
  const response = await apiClient.get<WorkspaceSummary[]>("/workspaces");
  return response.data;
}
