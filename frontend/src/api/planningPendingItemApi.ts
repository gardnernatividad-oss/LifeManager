import { apiClient } from "./client";
import type { CategoryOption, CategoryOptionPage, PendingItemCreatePayload, PendingItemListParams, PendingItemListResponse, PendingItemUpdatePayload, PlanningPendingItem } from "../types/planningPendingItem";
import { env } from "../utils/env";

const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();
export async function listCategoryOptionPage(page = 1): Promise<CategoryOptionPage> { return (await apiClient.get<CategoryOptionPage>(apiUrl("/categories"), { params: { page, page_size: 100 } })).data; }
export async function listAllCategoryOptions(): Promise<CategoryOption[]> {
  const first = await listCategoryOptionPage(1);
  const items = [...first.items];
  for (let page = 2; page <= first.total_pages; page += 1) {
    const result = await listCategoryOptionPage(page);
    items.push(...result.items);
  }
  return items;
}
export async function listPlanningPendingItems(params: PendingItemListParams): Promise<PendingItemListResponse> { return (await apiClient.get<PendingItemListResponse>(apiUrl("/pending-items"), { params })).data; }
export async function createPlanningPendingItem(payload: PendingItemCreatePayload): Promise<PlanningPendingItem> { return (await apiClient.post<PlanningPendingItem>(apiUrl("/pending-items"), payload)).data; }
export async function updatePlanningPendingItem(id: string, payload: PendingItemUpdatePayload): Promise<PlanningPendingItem> { return (await apiClient.patch<PlanningPendingItem>(apiUrl(`/pending-items/${id}`), payload)).data; }
