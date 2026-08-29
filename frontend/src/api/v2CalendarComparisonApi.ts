import { apiClient } from "./client";
import { env } from "../utils/env";
import type { CalendarComparison, CalendarComparisonMulti, CalendarVisibility, CalendarVisibilitySetting } from "../types/v2CalendarComparison";

const url = (workspaceId: string, suffix: string) => new URL(`/api/v2/workspaces/${workspaceId}/${suffix}`, env.apiBaseUrl).toString();

export async function getCalendarComparison(workspaceId: string, targetUserId: string, from: string, to: string): Promise<CalendarComparison> {
  return (await apiClient.get<CalendarComparison>(url(workspaceId, "calendar-comparison"), {
    params: { target_user_id: targetUserId, from, to },
  })).data;
}

export async function getCalendarComparisonMulti(workspaceId: string, targetUserIds: string[], from: string, to: string): Promise<CalendarComparisonMulti> {
  return (await apiClient.get<CalendarComparisonMulti>(url(workspaceId, "calendar-comparison/multi"), {
    params: { target_user_ids: targetUserIds, from, to }, paramsSerializer: { indexes: null },
  })).data;
}

export async function getCalendarVisibility(workspaceId: string): Promise<CalendarVisibilitySetting> {
  return (await apiClient.get<CalendarVisibilitySetting>(url(workspaceId, "calendar-visibility"))).data;
}

export async function setCalendarVisibility(workspaceId: string, visibility: CalendarVisibility, lockVersion: number): Promise<CalendarVisibilitySetting> {
  return (await apiClient.patch<CalendarVisibilitySetting>(url(workspaceId, "calendar-visibility"), {
    visibility, lock_version: lockVersion,
  })).data;
}
