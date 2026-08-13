import { apiClient } from "./client";
import type {
  MasterTaskListResponse, MasterTaskOption, PlanningTask, PlanningTaskListParams,
  PlanningTaskListResponse, TaskBulkCreatePayload, TaskBulkCreateResponse,
  TaskCreatePayload, TaskDeleteItem, TaskUpdatePayload
} from "../types/planningTask";
import { env } from "../utils/env";

const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();

export async function listMasterTaskPage(page = 1): Promise<MasterTaskListResponse> {
  const response = await apiClient.get<MasterTaskListResponse>(apiUrl("/master-tasks"), { params: { page, page_size: 100 } });
  return response.data;
}

export async function listAllMasterTasks(): Promise<MasterTaskOption[]> {
  const first = await listMasterTaskPage(1);
  const pages = await Promise.all(Array.from({ length: Math.max(0, first.total_pages - 1) }, (_, index) => listMasterTaskPage(index + 2)));
  return [first, ...pages].flatMap((result) => result.items);
}

export async function listPlanningTasks(params: PlanningTaskListParams): Promise<PlanningTaskListResponse> {
  const response = await apiClient.get<PlanningTaskListResponse>(apiUrl("/tasks"), { params });
  return response.data;
}

export async function createPlanningTask(payload: TaskCreatePayload): Promise<PlanningTask> {
  return (await apiClient.post<PlanningTask>(apiUrl("/tasks"), payload)).data;
}

export async function createPlanningTasksBulk(payload: TaskBulkCreatePayload): Promise<TaskBulkCreateResponse> {
  return (await apiClient.post<TaskBulkCreateResponse>(apiUrl("/tasks/bulk"), payload)).data;
}

export async function updatePlanningTask(taskId: string, payload: TaskUpdatePayload): Promise<PlanningTask> {
  return (await apiClient.patch<PlanningTask>(apiUrl(`/tasks/${taskId}`), payload)).data;
}

export async function deletePlanningTask(taskId: string, lockVersion: number): Promise<void> {
  await apiClient.delete(apiUrl(`/tasks/${taskId}`), { params: { lock_version: lockVersion } });
}

export async function deletePlanningTasksBulk(items: TaskDeleteItem[]): Promise<{ deleted_count: number }> {
  return (await apiClient.post<{ deleted_count: number }>(apiUrl("/tasks/bulk-delete"), { items })).data;
}
