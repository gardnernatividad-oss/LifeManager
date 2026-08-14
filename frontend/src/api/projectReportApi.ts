import type { ProjectReportParams, ProjectReportResponse } from "../types/projectReport";
import { env } from "../utils/env";
import { apiClient } from "./client";

const url = new URL("/api/v1/reports/projects", env.apiBaseUrl).toString();

export async function getProjectReport(
  params: ProjectReportParams,
): Promise<ProjectReportResponse> {
  return (await apiClient.get<ProjectReportResponse>(url, { params })).data;
}
