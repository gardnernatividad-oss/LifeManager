import axios from "axios";

import { apiClient } from "./client";
import type { DailyFormDefinition, DailyFormSubmission, DailyFormSubmissionPayload } from "../types/dailyForm";

export async function getDailyFormDefinition(workspaceId: string): Promise<DailyFormDefinition | null> {
  try { return (await apiClient.get<DailyFormDefinition>(`/workspaces/${workspaceId}/daily-form`)).data; }
  catch (error) { if (axios.isAxiosError(error) && error.response?.status === 404) return null; throw error; }
}

export async function getDailyFormSubmission(workspaceId: string, date: string): Promise<DailyFormSubmission | null> {
  try { return (await apiClient.get<DailyFormSubmission>(`/workspaces/${workspaceId}/daily-form/submissions/${date}`)).data; }
  catch (error) { if (axios.isAxiosError(error) && error.response?.status === 404) return null; throw error; }
}

export async function putDailyFormSubmission(workspaceId: string, date: string, payload: DailyFormSubmissionPayload): Promise<DailyFormSubmission> {
  return (await apiClient.put<DailyFormSubmission>(`/workspaces/${workspaceId}/daily-form/submissions/${date}`, payload)).data;
}
