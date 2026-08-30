import { apiClient } from "./client";
import type { ReviewBlockSaveResponse, ReviewPendingBatch, ReviewProjectStageBatch, ReviewRead, ReviewTaskBatch } from "../types/review";
import { env } from "../utils/env";

const reviewUrl = new URL("/api/v2/review", env.apiBaseUrl).toString();

export async function getReview(): Promise<ReviewRead> {
  return (await apiClient.get<ReviewRead>(reviewUrl)).data;
}

export async function saveReviewTasks(payload: ReviewTaskBatch): Promise<ReviewBlockSaveResponse> {
  return (await apiClient.post<ReviewBlockSaveResponse>(`${reviewUrl}/tasks`, payload)).data;
}

export async function saveReviewPendingItems(payload: ReviewPendingBatch): Promise<ReviewBlockSaveResponse> {
  return (await apiClient.post<ReviewBlockSaveResponse>(`${reviewUrl}/pending-items`, payload)).data;
}

export async function saveReviewProjectStages(payload: ReviewProjectStageBatch): Promise<ReviewBlockSaveResponse> {
  return (await apiClient.post<ReviewBlockSaveResponse>(`${reviewUrl}/project-stages`, payload)).data;
}
