import { apiClient } from "./client";
import { env } from "../utils/env";
import type { V2PendingItem, V2PendingItemCreate, V2PendingItemList, V2PendingItemUpdate } from "../types/v2PendingItem";

const url = (workspaceId: string, suffix = "") => new URL(`/api/v2/workspaces/${workspaceId}/pending-items${suffix}`, env.apiBaseUrl).toString();
export async function listV2PendingItems(workspaceId: string, page: number, pageSize: number): Promise<V2PendingItemList> { return (await apiClient.get<V2PendingItemList>(url(workspaceId), { params: { page, page_size: pageSize } })).data; }
export async function createV2PendingItem(workspaceId: string, payload: V2PendingItemCreate): Promise<V2PendingItem> { return (await apiClient.post<V2PendingItem>(url(workspaceId), payload)).data; }
export async function updateV2PendingItem(workspaceId: string, itemId: string, payload: V2PendingItemUpdate): Promise<V2PendingItem> { return (await apiClient.patch<V2PendingItem>(url(workspaceId, `/${itemId}`), payload)).data; }
export async function updateV2PendingItemProgress(workspaceId: string, itemId: string, progress: number, lockVersion: number): Promise<V2PendingItem> { return (await apiClient.post<V2PendingItem>(url(workspaceId, `/${itemId}/progress`), { progress, lock_version: lockVersion })).data; }
export async function correctV2PendingItem(workspaceId: string, itemId: string, progress: number, lockVersion: number): Promise<V2PendingItem> { return (await apiClient.post<V2PendingItem>(url(workspaceId, `/${itemId}/correction`), { progress, lock_version: lockVersion })).data; }
export async function deactivateV2PendingItem(workspaceId: string, itemId: string, lockVersion: number): Promise<V2PendingItem> { return (await apiClient.post<V2PendingItem>(url(workspaceId, `/${itemId}/deactivate`), { lock_version: lockVersion })).data; }
export async function reactivateV2PendingItem(workspaceId: string, itemId: string, plannedDate: string, lockVersion: number): Promise<V2PendingItem> { return (await apiClient.post<V2PendingItem>(url(workspaceId, `/${itemId}/reactivate`), { planned_date: plannedDate, lock_version: lockVersion })).data; }
export async function deleteV2PendingItem(workspaceId: string, itemId: string, lockVersion: number): Promise<void> { await apiClient.delete(url(workspaceId, `/${itemId}`), { params: { lock_version: lockVersion } }); }
