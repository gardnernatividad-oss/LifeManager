import { apiClient } from "./client";
import type { V2ReportFilters, V2ReportSummary } from "../types/v2Report";
import { env } from "../utils/env";

const reportSummaryUrl = (workspaceId: string) =>
  new URL(`/api/v2/workspaces/${workspaceId}/reports/summary`, env.apiBaseUrl).toString();

export async function getV2ReportSummary(
  workspaceId: string,
  filters: V2ReportFilters,
): Promise<V2ReportSummary> {
  return (await apiClient.get<V2ReportSummary>(reportSummaryUrl(workspaceId), { params: filters })).data;
}
