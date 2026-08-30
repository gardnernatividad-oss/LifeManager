import { apiClient } from "./client";
import type { HomeSummary } from "../types/home";
import type { V2HomeSummary } from "../types/v2Home";
import { env } from "../utils/env";

const homeUrl = new URL("/api/v1/home", env.apiBaseUrl).toString();
const v2HomeUrl = new URL("/api/v2/home", env.apiBaseUrl).toString();

export async function getHomeSummary(): Promise<HomeSummary> {
  const response = await apiClient.get<HomeSummary>(homeUrl);
  return response.data;
}

export async function getV2HomeSummary(): Promise<V2HomeSummary> {
  const response = await apiClient.get<V2HomeSummary>(v2HomeUrl);
  return response.data;
}
