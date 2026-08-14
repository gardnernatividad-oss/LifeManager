import type {
  PendingItemReportParams,
  PendingItemReportResponse,
} from "../types/pendingItemReport";
import { env } from "../utils/env";
import { apiClient } from "./client";

const url = new URL("/api/v1/reports/pending-items", env.apiBaseUrl).toString();

export async function getPendingItemReport(
  params: PendingItemReportParams,
): Promise<PendingItemReportResponse> {
  return (await apiClient.get<PendingItemReportResponse>(url, { params })).data;
}
