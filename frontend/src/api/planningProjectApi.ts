import { apiClient } from "./client";
import type { PlanningProjectCreatePayload, PlanningProjectDetail, PlanningProjectListParams, PlanningProjectListResponse, PlanningProjectStep, PlanningProjectUpdatePayload, PlanningStepInput, PlanningStepUpdatePayload } from "../types/planningProject";
import { env } from "../utils/env";

const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();
export async function listPlanningProjects(params: PlanningProjectListParams): Promise<PlanningProjectListResponse> { return (await apiClient.get<PlanningProjectListResponse>(apiUrl("/projects"), { params })).data; }
export async function getPlanningProject(id: string): Promise<PlanningProjectDetail> { return (await apiClient.get<PlanningProjectDetail>(apiUrl(`/projects/${id}`))).data; }
export async function createPlanningProject(payload: PlanningProjectCreatePayload): Promise<PlanningProjectDetail> { return (await apiClient.post<PlanningProjectDetail>(apiUrl("/projects"), payload)).data; }
export async function updatePlanningProject(id: string, payload: PlanningProjectUpdatePayload): Promise<PlanningProjectDetail> { return (await apiClient.patch<PlanningProjectDetail>(apiUrl(`/projects/${id}`), payload)).data; }
export async function createPlanningProjectStep(projectId: string, payload: PlanningStepInput): Promise<PlanningProjectStep> { return (await apiClient.post<PlanningProjectStep>(apiUrl(`/projects/${projectId}/steps`), payload)).data; }
export async function updatePlanningProjectStep(projectId: string, stepId: string, payload: PlanningStepUpdatePayload): Promise<PlanningProjectStep> { return (await apiClient.patch<PlanningProjectStep>(apiUrl(`/projects/${projectId}/steps/${stepId}`), payload)).data; }
