import { apiClient } from "./client";
import type { PlanningProject, PlanningProjectDetail, PlanningProjectListParams, PlanningProjectListResponse, ProjectStepTrackingUpdate, ProjectTrackingBatchResponse } from "../types/planningProject";
import { env } from "../utils/env";
const url = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();
export async function listTrackingProjects(params: PlanningProjectListParams): Promise<PlanningProjectListResponse> { return (await apiClient.get<PlanningProjectListResponse>(url("/projects"), { params })).data; }
export async function getTrackingProject(id: string): Promise<PlanningProjectDetail> { return (await apiClient.get<PlanningProjectDetail>(url(`/projects/${id}`))).data; }
export async function saveProjectGeneralComment(id: string, generalComment: string | null, lockVersion: number): Promise<PlanningProject> { return (await apiClient.patch<PlanningProject>(url(`/projects/${id}/tracking-general`), { general_comment: generalComment, lock_version: lockVersion })).data; }
export async function saveProjectStepTracking(id: string, projectLockVersion: number, items: ProjectStepTrackingUpdate[]): Promise<ProjectTrackingBatchResponse> { return (await apiClient.patch<ProjectTrackingBatchResponse>(url(`/projects/${id}/tracking`), { project_lock_version: projectLockVersion, items })).data; }
