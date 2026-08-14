import { createContext } from "react";

import type {
  AuthenticatedUser,
  LoginCredentials,
  WorkspaceSummary
} from "../types/auth";

export interface AuthState {
  accessToken: string | null;
  user: AuthenticatedUser | null;
  workspace: WorkspaceSummary | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  setWorkspace: (workspace: WorkspaceSummary | null) => void;
  clearSession: () => void;
  setAuthenticatedUser: (user: AuthenticatedUser) => void;
}

export const AuthContext = createContext<AuthState | undefined>(undefined);
