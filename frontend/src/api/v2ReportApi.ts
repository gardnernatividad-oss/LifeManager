import { apiClient } from "./client";
import type { V2ActivityReport, V2PendingReport, V2ProjectReport, V2ReportFilters, V2ReportSummary, V2TaskReport } from "../types/v2Report";
import { env } from "../utils/env";

const reportSummaryUrl = (workspaceId: string) =>
  new URL(`/api/v2/workspaces/${workspaceId}/reports/summary`, env.apiBaseUrl).toString();

export async function getV2ReportSummary(
  workspaceId: string,
  filters: V2ReportFilters,
): Promise<V2ReportSummary> {
  return (await apiClient.get<V2ReportSummary>(reportSummaryUrl(workspaceId), { params: filters })).data;
}

export interface V2TaskReportFilters extends V2ReportFilters { master_task_id?: string; custom_tasks?: boolean }
async function getReport<T>(workspaceId: string, section: string, filters: object): Promise<T> {
  const endpoint = new URL(`/api/v2/workspaces/${workspaceId}/reports/${section}`, env.apiBaseUrl).toString();
  return (await apiClient.get<T>(endpoint, { params: filters })).data;
}
export const getV2TaskReport = (workspaceId: string, filters: V2TaskReportFilters) => getReport<V2TaskReport>(workspaceId, "tasks", filters);
export const getV2PendingReport = (workspaceId: string, filters: V2ReportFilters) => getReport<V2PendingReport>(workspaceId, "pending-items", filters);
export const getV2ProjectReport = (workspaceId: string, filters: V2ReportFilters) => getReport<V2ProjectReport>(workspaceId, "projects", filters);
export interface V2ActivityReportFilters extends V2ReportFilters { activity_master_id?: string; custom_activities?: boolean }
export const getV2ActivityReport = (workspaceId: string, filters: V2ActivityReportFilters) => getReport<V2ActivityReport>(workspaceId, "activities", filters);
