import { apiClient } from "./client"; import type { TaskReportParams,TaskReportResponse } from "../types/taskReport"; import { env } from "../utils/env";
const url=new URL("/api/v1/reports/tasks",env.apiBaseUrl).toString(); export async function getTaskReport(params:TaskReportParams):Promise<TaskReportResponse>{return(await apiClient.get<TaskReportResponse>(url,{params})).data;}
