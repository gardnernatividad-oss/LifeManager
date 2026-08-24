import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useAuth } from "../hooks/useAuth";
import type { AuthState } from "../store/auth-context";
import { testUser } from "../test/testUser";
import { ProtectedRoute, PublicOnlyRoute } from "./RouteGuards";

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));

function authState(overrides: Partial<AuthState> = {}): AuthState {
  return {
    user: null,
    workspace: null,
    isAuthenticated: false,
    isInitializing: false,
    login: vi.fn(),
    logout: vi.fn(),
    setWorkspace: vi.fn(),
    clearSession: vi.fn(),
    setAuthenticatedUser: vi.fn(),
    ...overrides
  };
}

function LoginDestination() {
  const location = useLocation();
  const state = location.state as { from?: { pathname?: string; search?: string } } | null;
  return <span>Login from {state?.from?.pathname}{state?.from?.search}</span>;
}

describe("authentication route guards", () => {
  it("redirects an unauthenticated protected route and preserves its location", () => {
    vi.mocked(useAuth).mockReturnValue(authState());
    render(
      <MemoryRouter initialEntries={["/revision?view=today"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/revision" element={<span>Review</span>} />
          </Route>
          <Route path="/login" element={<LoginDestination />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Login from /revision?view=today")).toBeInTheDocument();
  });

  it("redirects an authenticated user away from Login", () => {
    vi.mocked(useAuth).mockReturnValue(authState({
      user: testUser,
      isAuthenticated: true
    }));
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<span>Login</span>} />
          </Route>
          <Route path="/inicio" element={<span>Inicio</span>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Inicio")).toBeInTheDocument();
  });

  it("does not render protected content during initialization", () => {
    vi.mocked(useAuth).mockReturnValue(authState({ isInitializing: true }));
    render(
      <MemoryRouter initialEntries={["/revision"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/revision" element={<span>Review</span>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Comprobando sesión…")).toBeInTheDocument();
    expect(screen.queryByText("Tasks")).not.toBeInTheDocument();
  });
});
