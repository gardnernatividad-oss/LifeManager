import { apiClient } from "./client";
import { env } from "../utils/env";
import type { MyCalendarResponse } from "../types/v2Calendar";

export async function getMyCalendar(rangeStart: string, rangeEnd: string): Promise<MyCalendarResponse> {
  const url = new URL("/api/v2/calendar/me", env.apiBaseUrl).toString();
  return (await apiClient.get<MyCalendarResponse>(url, { params: { from: rangeStart, to: rangeEnd } })).data;
}
