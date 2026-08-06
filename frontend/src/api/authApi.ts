import { apiClient } from "./client";
import type { AuthenticatedUser, LoginCredentials, TokenResponse } from "../types/auth";

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>("/auth/login", credentials);
  return response.data;
}

export async function getAuthenticatedUser(): Promise<AuthenticatedUser> {
  const response = await apiClient.get<AuthenticatedUser>("/auth/me");
  return response.data;
}
