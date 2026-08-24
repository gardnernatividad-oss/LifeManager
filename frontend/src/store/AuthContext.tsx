import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type PropsWithChildren } from "react";

import {
  getAuthenticatedUser,
  login as requestLogin,
  logout as requestLogout
} from "../api/authApi";
import { configureSessionTransport } from "../services/sessionTransport";
import type { AuthenticatedUser, LoginCredentials, WorkspaceSummary } from "../types/auth";
import { AuthContext, type AuthState } from "./auth-context";

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const clearSession = useCallback(() => {
    setUser(null);
    setWorkspace(null);
    queryClient.clear();
  }, [queryClient]);

  const logout = useCallback(async () => {
    try {
      await requestLogout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    try {
      const authenticatedUser = await requestLogin(credentials);
      setUser(authenticatedUser);
    } catch (error) {
      clearSession();
      throw error;
    }
  }, [clearSession]);

  useEffect(() => {
    configureSessionTransport({
      onUnauthorized: clearSession
    });
  }, [clearSession]);

  useEffect(() => {
    let active = true;

    async function initializeSession() {
      try {
        const authenticatedUser = await getAuthenticatedUser();
        if (active) {
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
      user,
      workspace,
      isAuthenticated: Boolean(user),
      isInitializing,
      login,
      logout,
      setWorkspace,
      clearSession,
      setAuthenticatedUser: setUser
    }),
    [clearSession, isInitializing, login, logout, user, workspace]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
