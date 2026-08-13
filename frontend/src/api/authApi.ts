import { apiClient } from "./client";
import type { AuthenticatedUser, LoginCredentials, TokenResponse } from "../types/auth";
import { env } from "../utils/env";

const versionedAuthUrl = (resource: "login" | "me") =>
  new URL(`/api/v1/auth/${resource}`, env.apiBaseUrl).toString();

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>(versionedAuthUrl("login"), credentials);
  return response.data;
}

export async function getAuthenticatedUser(): Promise<AuthenticatedUser> {
  const response = await apiClient.get<AuthenticatedUser>(versionedAuthUrl("me"));
  return response.data;
}
