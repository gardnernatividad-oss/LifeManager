import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type PropsWithChildren } from "react";

import { getAuthenticatedUser, login as requestLogin } from "../api/authApi";
import {
  configureAuthTransport,
  readAccessToken,
  removeAccessToken,
  storeAccessToken
} from "../services/authToken";
import type { AuthenticatedUser, LoginCredentials, WorkspaceSummary } from "../types/auth";
import { AuthContext, type AuthState } from "./auth-context";

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [accessToken, setAccessToken] = useState<string | null>(() => readAccessToken());
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const clearSession = useCallback(() => {
    removeAccessToken();
    setAccessToken(null);
    setUser(null);
    setWorkspace(null);
    queryClient.clear();
  }, [queryClient]);

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokenResponse = await requestLogin(credentials);
    storeAccessToken(tokenResponse.access_token);
    setAccessToken(tokenResponse.access_token);

    try {
      const authenticatedUser = await getAuthenticatedUser();
      setUser(authenticatedUser);
    } catch (error) {
      clearSession();
      throw error;
    }
  }, [clearSession]);

  useEffect(() => {
    configureAuthTransport({
      getAccessToken: readAccessToken,
      onUnauthorized: clearSession
    });
  }, [clearSession]);

  useEffect(() => {
    let active = true;

    async function initializeSession() {
      const storedToken = readAccessToken();
      if (!storedToken) {
        if (active) {
          setIsInitializing(false);
        }
        return;
      }

      try {
        const authenticatedUser = await getAuthenticatedUser();
        if (active) {
          setAccessToken(storedToken);
          setUser(authenticatedUser);
        }
      } catch {
        if (active) {
          clearSession();
        }
      } finally {
        if (active) {
          setIsInitializing(false);
        }
      }
    }

    void initializeSession();
    return () => {
      active = false;
    };
  }, [clearSession]);

  const value = useMemo<AuthState>(
    () => ({
      accessToken,
      user,
      workspace,
      isAuthenticated: Boolean(accessToken && user),
      isInitializing,
      login,
      logout,
      setWorkspace,
      clearSession
    }),
    [accessToken, clearSession, isInitializing, login, logout, user, workspace]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
