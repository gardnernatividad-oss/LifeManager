import { apiClient } from "./client";
import type { PendingItemListResponse, PendingItemTrackingBatchResponse, PendingItemTrackingUpdate, TrackingPendingItemListParams } from "../types/planningPendingItem";
import { env } from "../utils/env";

const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();

export async function listTrackingPendingItems(params: TrackingPendingItemListParams): Promise<PendingItemListResponse> {
  return (await apiClient.get<PendingItemListResponse>(apiUrl("/pending-items"), { params })).data;
}

export async function saveTrackingPendingItems(items: PendingItemTrackingUpdate[]): Promise<PendingItemTrackingBatchResponse> {
  return (await apiClient.patch<PendingItemTrackingBatchResponse>(apiUrl("/pending-items/tracking"), { items })).data;
}
