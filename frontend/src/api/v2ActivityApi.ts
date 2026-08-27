import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2Activity, V2ActivityCreate, V2ActivityFilters, V2ActivityList, V2ActivityUpdate } from "../types/v2Activity";

const url = (workspaceId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/activities${suffix}`, env.apiBaseUrl).toString();

export async function listV2Activities(workspaceId: string, filters: V2ActivityFilters): Promise<V2ActivityList> {
  return (await apiClient.get<V2ActivityList>(url(workspaceId), { params: filters })).data;
}
export async function createV2Activity(workspaceId: string, payload: V2ActivityCreate): Promise<V2Activity> {
  return (await apiClient.post<V2Activity>(url(workspaceId), payload)).data;
}
export async function updateV2Activity(workspaceId: string, activityId: string, payload: V2ActivityUpdate): Promise<V2Activity> {
  return (await apiClient.patch<V2Activity>(url(workspaceId, `/${activityId}`), payload)).data;
}
export async function deleteV2Activity(workspaceId: string, activityId: string, lockVersion: number): Promise<void> {
  await apiClient.delete(url(workspaceId, `/${activityId}`), { params: { lock_version: lockVersion } });
}
export async function leaveV2Activity(workspaceId: string, activityId: string, lockVersion: number): Promise<V2Activity> {
  return (await apiClient.post<V2Activity>(url(workspaceId, `/${activityId}/leave`), { lock_version: lockVersion })).data;
}
