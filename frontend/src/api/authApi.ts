import { apiClient } from "./client";
import type { AuthenticatedUser, LoginCredentials, ProfileUpdatePayload, RegistrationPayload, TokenResponse } from "../types/auth";
import { env } from "../utils/env";

const versionedAuthUrl = (resource: "login" | "me" | "register") =>
  new URL(`/api/v1/auth/${resource}`, env.apiBaseUrl).toString();

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>(versionedAuthUrl("login"), credentials);
  return response.data;
}

export async function getAuthenticatedUser(): Promise<AuthenticatedUser> {
  const response = await apiClient.get<AuthenticatedUser>(versionedAuthUrl("me"));
  return response.data;
}

export async function registerUser(payload: RegistrationPayload): Promise<AuthenticatedUser> {
  const response = await apiClient.post<AuthenticatedUser>(versionedAuthUrl("register"), payload);
  return response.data;
}

export async function updateAuthenticatedUser(payload: ProfileUpdatePayload): Promise<AuthenticatedUser> {
  const response = await apiClient.patch<AuthenticatedUser>(versionedAuthUrl("me"), payload);
  return response.data;
}

export async function listTimezones(): Promise<string[]> {
  const url = new URL("/api/v1/timezones", env.apiBaseUrl).toString();
  const response = await apiClient.get<{ items: string[] }>(url);
  return response.data.items;
}
