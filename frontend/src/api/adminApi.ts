import type {
  AdminAccountRequest,
  AdminAccountRequestList,
  AdminUser,
  AdminUserFilters,
  AdminUserList,
} from "../types/admin";
import { env } from "../utils/env";
import { apiClient } from "./client";

const v2 = (path: string) => new URL(`/api/v2/admin${path}`, env.apiBaseUrl).toString();

export async function listAccountRequests(): Promise<AdminAccountRequestList> {
  return (await apiClient.get<AdminAccountRequestList>(v2("/account-requests"))).data;
}

export async function approveAccountRequest(userId: string): Promise<AdminAccountRequest> {
  return (await apiClient.post<AdminAccountRequest>(v2(`/account-requests/${userId}/approve`))).data;
}

export async function rejectAccountRequest(userId: string, reason?: string): Promise<AdminAccountRequest> {
  return (await apiClient.post<AdminAccountRequest>(v2(`/account-requests/${userId}/reject`), { reason: reason || null })).data;
}

export async function listAdminUsers(filters: AdminUserFilters): Promise<AdminUserList> {
  const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.page_size) });
  if (filters.account_status) params.set("account_status", filters.account_status);
  if (filters.search) params.set("search", filters.search);
  return (await apiClient.get<AdminUserList>(`${v2("/users")}?${params.toString()}`)).data;
}

async function changeState(user: AdminUser, action: "disable" | "reactivate"): Promise<AdminUser> {
  return (await apiClient.post<AdminUser>(v2(`/users/${user.id}/${action}`), { lock_version: user.lock_version })).data;
}

export const disableAdminUser = (user: AdminUser) => changeState(user, "disable");
export const reactivateAdminUser = (user: AdminUser) => changeState(user, "reactivate");
