import { apiClient } from "./client";
import type { ReviewRead, ReviewSave, ReviewSaveResponse } from "../types/review";
import { env } from "../utils/env";

const reviewUrl = new URL("/api/v1/review", env.apiBaseUrl).toString();

export async function getReview(): Promise<ReviewRead> {
  const response = await apiClient.get<ReviewRead>(reviewUrl);
  return response.data;
}

export async function saveReview(review: ReviewSave): Promise<ReviewSaveResponse> {
  const response = await apiClient.patch<ReviewSaveResponse>(reviewUrl, review);
  return response.data;
}
