import { useMemo, useState, type PropsWithChildren } from "react";

import type { UserSummary, WorkspaceSummary } from "../types/auth";
import { AuthContext, type AuthState } from "./auth-context";

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserSummary | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);

  const value = useMemo<AuthState>(
    () => ({
      accessToken,
      user,
      workspace,
      setAccessToken,
      setUser,
      setWorkspace,
      clearSession: () => {
        setAccessToken(null);
        setUser(null);
        setWorkspace(null);
      }
    }),
    [accessToken, user, workspace]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
