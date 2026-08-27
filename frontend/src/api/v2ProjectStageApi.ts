import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2ProjectStage, V2ProjectStageCreate, V2ProjectStageHistoryList, V2ProjectStageList, V2ProjectStageTracking, V2ProjectStageUpdate } from "../types/v2ProjectStage";
const url = (workspaceId: string, projectId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/projects/${projectId}/stages${suffix}`, env.apiBaseUrl).toString();
export async function listV2ProjectStages(workspaceId: string, projectId: string): Promise<V2ProjectStageList> { return (await apiClient.get<V2ProjectStageList>(url(workspaceId, projectId))).data; }
export async function getV2ProjectStage(workspaceId: string, projectId: string, stageId: string): Promise<V2ProjectStage> { return (await apiClient.get<V2ProjectStage>(url(workspaceId, projectId, `/${stageId}`))).data; }
export async function createV2ProjectStage(workspaceId: string, projectId: string, payload: V2ProjectStageCreate): Promise<V2ProjectStage> { return (await apiClient.post<V2ProjectStage>(url(workspaceId, projectId), payload)).data; }
export async function updateV2ProjectStage(workspaceId: string, projectId: string, stageId: string, payload: V2ProjectStageUpdate): Promise<V2ProjectStage> { return (await apiClient.patch<V2ProjectStage>(url(workspaceId, projectId, `/${stageId}`), payload)).data; }
export async function updateV2ProjectStageProgress(workspaceId: string, projectId: string, stageId: string, payload: V2ProjectStageTracking): Promise<V2ProjectStage> { return (await apiClient.post<V2ProjectStage>(url(workspaceId, projectId, `/${stageId}/progress`), payload)).data; }
export async function listV2ProjectStageHistory(workspaceId: string, projectId: string, stageId: string): Promise<V2ProjectStageHistoryList> { return (await apiClient.get<V2ProjectStageHistoryList>(url(workspaceId, projectId, `/${stageId}/history`))).data; }
