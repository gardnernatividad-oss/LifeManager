import { apiClient } from "./client";
import type { V2CatalogItem, V2CatalogList, V2Category } from "../types/v2Catalog";
import { env } from "../utils/env";

export type CatalogKind = "categories" | "master-tasks" | "activity-masters";

const url = (workspaceId: string, kind: CatalogKind, suffix = "") =>
  new URL(`/api/v2/workspaces/${workspaceId}/${kind}${suffix}`, env.apiBaseUrl).toString();

export async function listV2Catalog<T extends V2Category>(workspaceId: string, kind: CatalogKind, params: { active?: boolean; category_id?: string; search?: string }): Promise<V2CatalogList<T>> {
  return (await apiClient.get<V2CatalogList<T>>(url(workspaceId, kind), { params })).data;
}

export async function createV2Catalog<T extends V2Category>(workspaceId: string, kind: CatalogKind, payload: { name: string; category_id?: string }): Promise<T> {
  return (await apiClient.post<T>(url(workspaceId, kind), payload)).data;
}

export async function updateV2Catalog<T extends V2Category>(workspaceId: string, kind: CatalogKind, id: string, payload: { name?: string; category_id?: string; lock_version: number }): Promise<T> {
  return (await apiClient.patch<T>(url(workspaceId, kind, `/${id}`), payload)).data;
}

export async function setV2CatalogActive<T extends V2Category>(workspaceId: string, kind: CatalogKind, item: T, active: boolean): Promise<T> {
  const action = active ? "activate" : "deactivate";
  return (await apiClient.post<T>(url(workspaceId, kind, `/${item.id}/${action}`), { lock_version: item.lock_version })).data;
}

export type { V2CatalogItem, V2Category };
