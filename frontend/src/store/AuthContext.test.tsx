import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../api/authApi";
import { useAuth } from "../hooks/useAuth";
import { handleUnauthorized } from "../services/sessionTransport";
import { testUser } from "../test/testUser";
import { AuthProvider } from "./AuthContext";

vi.mock("../api/authApi", () => ({ login: vi.fn(), logout: vi.fn(), getAuthenticatedUser: vi.fn() }));

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function TestProviders({ children }: PropsWithChildren) {
  return <QueryClientProvider client={queryClient}><AuthProvider>{children}</AuthProvider></QueryClientProvider>;
}

function AuthHarness() {
  const auth = useAuth();
  return <div>
    <span data-testid="initializing">{String(auth.isInitializing)}</span>
    <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
    <span data-testid="email">{auth.user?.email ?? "none"}</span>
    <button type="button" onClick={() => void auth.login({ email: "ada@example.com", password: "secret" })}>Login</button>
    <button type="button" onClick={() => void auth.logout()}>Logout</button>
  </div>;
}

describe("AuthProvider cookie session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
    vi.mocked(authApi.getAuthenticatedUser).mockRejectedValue(new Error("No session"));
  });

  it("logs in using the safe user response without browser token storage", async () => {
    vi.mocked(authApi.login).mockResolvedValue(testUser);
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("initializing")).toHaveTextContent("false"));
    await userEvent.setup().click(screen.getByRole("button", { name: "Login" }));
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(screen.getByTestId("email")).toHaveTextContent(testUser.email);
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("restores the user from auth me on browser refresh", async () => {
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(authApi.getAuthenticatedUser).toHaveBeenCalledOnce();
  });

  it("logout calls backend and clears user and private query cache", async () => {
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    vi.mocked(authApi.logout).mockResolvedValue();
    queryClient.setQueryData(["private"], { secret: true });
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    await userEvent.setup().click(screen.getByRole("button", { name: "Logout" }));
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("false"));
    expect(authApi.logout).toHaveBeenCalledOnce();
    expect(queryClient.getQueryData(["private"])).toBeUndefined();
  });

  it("clears in-memory state when the transport reports 401", async () => {
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    await act(async () => handleUnauthorized());
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
  });
});
