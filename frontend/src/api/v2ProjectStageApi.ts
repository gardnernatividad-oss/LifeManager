import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2ProjectStage, V2ProjectStageCreate, V2ProjectStageList, V2ProjectStageUpdate } from "../types/v2ProjectStage";
const url = (workspaceId: string, projectId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/projects/${projectId}/stages${suffix}`, env.apiBaseUrl).toString();
export async function listV2ProjectStages(workspaceId: string, projectId: string): Promise<V2ProjectStageList> { return (await apiClient.get<V2ProjectStageList>(url(workspaceId, projectId))).data; }
export async function createV2ProjectStage(workspaceId: string, projectId: string, payload: V2ProjectStageCreate): Promise<V2ProjectStage> { return (await apiClient.post<V2ProjectStage>(url(workspaceId, projectId), payload)).data; }
export async function updateV2ProjectStage(workspaceId: string, projectId: string, stageId: string, payload: V2ProjectStageUpdate): Promise<V2ProjectStage> { return (await apiClient.patch<V2ProjectStage>(url(workspaceId, projectId, `/${stageId}`), payload)).data; }
export async function updateV2ProjectStageProgress(workspaceId: string, projectId: string, stageId: string, progress: number, lockVersion: number, projectLockVersion: number): Promise<V2ProjectStage> { return (await apiClient.post<V2ProjectStage>(url(workspaceId, projectId, `/${stageId}/progress`), { progress, lock_version: lockVersion, project_lock_version: projectLockVersion })).data; }
