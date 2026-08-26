import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2RecurringTaskCreate, V2RecurringTaskCreateResponse, V2Task, V2TaskCreate, V2TaskFilters, V2TaskList, V2TaskMutationScope, V2TaskResult, V2TaskUpdate } from "../types/v2Task";

const url = (workspaceId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/tasks${suffix}`, env.apiBaseUrl).toString();
export async function listV2Tasks(workspaceId: string, filters: V2TaskFilters): Promise<V2TaskList> { return (await apiClient.get<V2TaskList>(url(workspaceId), { params: filters })).data; }
export async function createV2Task(workspaceId: string, payload: V2TaskCreate): Promise<V2Task> { return (await apiClient.post<V2Task>(url(workspaceId), payload)).data; }
export async function createV2RecurringTasks(workspaceId: string, payload: V2RecurringTaskCreate): Promise<V2RecurringTaskCreateResponse> { return (await apiClient.post<V2RecurringTaskCreateResponse>(url(workspaceId, "/recurring"), payload)).data; }
export async function updateV2Task(workspaceId: string, taskId: string, payload: V2TaskUpdate): Promise<V2Task> { return (await apiClient.patch<V2Task>(url(workspaceId, `/${taskId}`), payload)).data; }
export async function resolveV2Task(workspaceId: string, taskId: string, result: V2TaskResult, lockVersion: number): Promise<V2Task> { const action = result === "COMPLETED" ? "complete" : "not-complete"; return (await apiClient.post<V2Task>(url(workspaceId, `/${taskId}/${action}`), { lock_version: lockVersion })).data; }
export async function deleteV2Task(workspaceId: string, taskId: string, lockVersion: number, scope: V2TaskMutationScope = "THIS"): Promise<void> { await apiClient.delete(url(workspaceId, `/${taskId}`), { params: { lock_version: lockVersion, scope } }); }
