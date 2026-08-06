import { createContext } from "react";

import type { UserSummary, WorkspaceSummary } from "../types/auth";

export interface AuthState {
  accessToken: string | null;
  user: UserSummary | null;
  workspace: WorkspaceSummary | null;
  setAccessToken: (token: string | null) => void;
  setUser: (user: UserSummary | null) => void;
  setWorkspace: (workspace: WorkspaceSummary | null) => void;
  clearSession: () => void;
}

export const AuthContext = createContext<AuthState | undefined>(undefined);
