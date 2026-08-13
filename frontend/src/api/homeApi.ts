import { apiClient } from "./client";
import type { HomeSummary } from "../types/home";
import { env } from "../utils/env";

const homeUrl = new URL("/api/v1/home", env.apiBaseUrl).toString();

export async function getHomeSummary(): Promise<HomeSummary> {
  const response = await apiClient.get<HomeSummary>(homeUrl);
  return response.data;
}
