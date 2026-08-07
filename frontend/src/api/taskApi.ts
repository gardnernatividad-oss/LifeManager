import { apiClient } from "./client";
import type { Task, TaskListParams, TaskListResponse, TaskUpdate, TaskWrite } from "../types/task";

const taskPath = (workspaceId: string) => `/workspaces/${workspaceId}/tasks`;

export async function listTasks(workspaceId: string, filters: TaskListParams): Promise<TaskListResponse> {
  const params: Record<string, string | number> = {
    page: filters.page,
    page_size: filters.pageSize,
    order_by: filters.orderBy,
    order_direction: filters.orderDirection
  };
  const optional = {
    search: filters.search.trim(), status: filters.status, outcome: filters.outcome,
    category_id: filters.categoryId, project_id: filters.projectId,
    scheduled_from: filters.scheduledFrom, scheduled_to: filters.scheduledTo
  };
  Object.entries(optional).forEach(([key, value]) => { if (value) params[key] = value; });
  return (await apiClient.get<TaskListResponse>(taskPath(workspaceId), { params })).data;
}

export async function createTask(workspaceId: string, payload: TaskWrite): Promise<Task> {
  return (await apiClient.post<Task>(taskPath(workspaceId), payload)).data;
}

export async function updateTask(workspaceId: string, taskId: string, payload: TaskUpdate): Promise<Task> {
  return (await apiClient.patch<Task>(`${taskPath(workspaceId)}/${taskId}`, payload)).data;
}

async function resolveTask(workspaceId: string, taskId: string, action: string): Promise<Task> {
  return (await apiClient.post<Task>(`${taskPath(workspaceId)}/${taskId}/${action}`)).data;
}

export const completeTask = (workspaceId: string, taskId: string) => resolveTask(workspaceId, taskId, "complete");
export const markTaskNotCompleted = (workspaceId: string, taskId: string) => resolveTask(workspaceId, taskId, "not-complete");
export const cancelTask = (workspaceId: string, taskId: string) => resolveTask(workspaceId, taskId, "cancel");
