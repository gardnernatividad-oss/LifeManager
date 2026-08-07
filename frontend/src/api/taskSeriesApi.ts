import { apiClient } from "./client";
import type { MaterializationResponse, SynchronizationResponse, TaskSeries, TaskSeriesListResponse, TaskSeriesWindow, TaskSeriesWrite } from "../types/taskSeries";

const path = (workspaceId: string) => `/workspaces/${workspaceId}/task-series`;

export async function listTaskSeries(workspaceId: string, isActive: boolean | null): Promise<TaskSeriesListResponse> {
  return (await apiClient.get<TaskSeriesListResponse>(path(workspaceId), { params: isActive === null ? undefined : { is_active: isActive } })).data;
}
export async function createTaskSeries(workspaceId: string, payload: TaskSeriesWrite): Promise<TaskSeries> {
  return (await apiClient.post<TaskSeries>(path(workspaceId), payload)).data;
}
export async function updateTaskSeries(workspaceId: string, seriesId: string, payload: TaskSeriesWrite): Promise<TaskSeries> {
  return (await apiClient.patch<TaskSeries>(`${path(workspaceId)}/${seriesId}`, payload)).data;
}
export async function activateTaskSeries(workspaceId: string, seriesId: string): Promise<TaskSeries> {
  return (await apiClient.post<TaskSeries>(`${path(workspaceId)}/${seriesId}/activate`)).data;
}
export async function deactivateTaskSeries(workspaceId: string, seriesId: string): Promise<TaskSeries> {
  return (await apiClient.post<TaskSeries>(`${path(workspaceId)}/${seriesId}/deactivate`)).data;
}
export async function materializeTaskSeries(workspaceId: string, seriesId: string, window: TaskSeriesWindow): Promise<MaterializationResponse> {
  return (await apiClient.post<MaterializationResponse>(`${path(workspaceId)}/${seriesId}/materialize`, window)).data;
}
export async function synchronizeTaskSeries(workspaceId: string, seriesId: string, window: TaskSeriesWindow): Promise<SynchronizationResponse> {
  return (await apiClient.post<SynchronizationResponse>(`${path(workspaceId)}/${seriesId}/synchronize`, window)).data;
}
