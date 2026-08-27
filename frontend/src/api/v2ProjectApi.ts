import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2Project, V2ProjectCreate, V2ProjectFilters, V2ProjectList, V2ProjectUpdate } from "../types/v2Project";

const url = (workspaceId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/projects${suffix}`, env.apiBaseUrl).toString();
export async function listV2Projects(workspaceId: string, filters: V2ProjectFilters): Promise<V2ProjectList> { return (await apiClient.get<V2ProjectList>(url(workspaceId), { params: filters })).data; }
export async function getV2Project(workspaceId: string, projectId: string): Promise<V2Project> { return (await apiClient.get<V2Project>(url(workspaceId, `/${projectId}`))).data; }
export async function createV2Project(workspaceId: string, payload: V2ProjectCreate): Promise<V2Project> { return (await apiClient.post<V2Project>(url(workspaceId), payload)).data; }
export async function updateV2Project(workspaceId: string, projectId: string, payload: V2ProjectUpdate): Promise<V2Project> { return (await apiClient.patch<V2Project>(url(workspaceId, `/${projectId}`), payload)).data; }
export async function deactivateV2Project(workspaceId: string, projectId: string, lockVersion: number): Promise<V2Project> { return (await apiClient.post<V2Project>(url(workspaceId, `/${projectId}/deactivate`), { lock_version: lockVersion })).data; }
export async function reactivateV2Project(workspaceId: string, projectId: string, lockVersion: number): Promise<V2Project> { return (await apiClient.post<V2Project>(url(workspaceId, `/${projectId}/reactivate`), { lock_version: lockVersion })).data; }
