import { apiClient } from "./client";
import type { AuthenticatedUser, LoginCredentials, ProfileUpdatePayload, RegistrationPayload } from "../types/auth";
import { env } from "../utils/env";

const v2AuthUrl = (resource: "login" | "logout" | "registration-requests") =>
  new URL(`/api/v2/auth/${resource}`, env.apiBaseUrl).toString();

export async function login(credentials: LoginCredentials): Promise<AuthenticatedUser> {
  const response = await apiClient.post<AuthenticatedUser>(v2AuthUrl("login"), credentials);
  return response.data;
}

export async function getAuthenticatedUser(): Promise<AuthenticatedUser> {
  const response = await apiClient.get<AuthenticatedUser>(
    new URL("/api/v2/me", env.apiBaseUrl).toString(),
  );
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post(v2AuthUrl("logout"));
}

export async function registerUser(payload: RegistrationPayload): Promise<void> {
  await apiClient.post(v2AuthUrl("registration-requests"), payload);
}

export async function updateAuthenticatedUser(payload: ProfileUpdatePayload): Promise<AuthenticatedUser> {
  const response = await apiClient.patch<AuthenticatedUser>(new URL("/api/v1/auth/me", env.apiBaseUrl).toString(), payload);
  return response.data;
}

export async function listTimezones(): Promise<string[]> {
  const url = new URL("/api/v1/timezones", env.apiBaseUrl).toString();
  const response = await apiClient.get<{ items: string[] }>(url);
  return response.data.items;
}
