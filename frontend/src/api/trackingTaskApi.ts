import { apiClient } from "./client";
import type { PlanningTask, PlanningTaskListParams, PlanningTaskListResponse } from "../types/planningTask";
import type { ReviewTaskResult } from "../types/review";
import { env } from "../utils/env";
const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();
export async function listTrackingTasks(params: PlanningTaskListParams): Promise<PlanningTaskListResponse> { return (await apiClient.get<PlanningTaskListResponse>(apiUrl("/tasks"), { params })).data; }
export async function updateTrackingTaskResult(id: string, result: ReviewTaskResult, lockVersion: number): Promise<PlanningTask> { return (await apiClient.patch<PlanningTask>(apiUrl(`/tasks/${id}/result`), { result, lock_version: lockVersion })).data; }
