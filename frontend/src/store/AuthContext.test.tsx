import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../api/authApi";
import { useAuth } from "../hooks/useAuth";
import {
  ACCESS_TOKEN_STORAGE_KEY,
  handleUnauthorized
} from "../services/authToken";
import { testUser } from "../test/testUser";
import { AuthProvider } from "./AuthContext";

vi.mock("../api/authApi", () => ({
  login: vi.fn(),
  getAuthenticatedUser: vi.fn()
}));

function TestProviders({ children }: PropsWithChildren) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

function AuthHarness() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="initializing">{String(auth.isInitializing)}</span>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="email">{auth.user?.email ?? "none"}</span>
      <span data-testid="workspace">{auth.workspace?.name ?? "none"}</span>
      <button
        type="button"
        onClick={() => void auth.login({ email: "ada@example.com", password: "secret" })}
      >
        Login
      </button>
      <button type="button" onClick={auth.logout}>Logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.mocked(authApi.login).mockReset();
    vi.mocked(authApi.getAuthenticatedUser).mockReset();
  });

  it("stores the token and loads the real user after login", async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: "valid-token", token_type: "bearer" });
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    const user = userEvent.setup();
    render(<AuthHarness />, { wrapper: TestProviders });

    await waitFor(() => expect(screen.getByTestId("initializing")).toHaveTextContent("false"));
    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(screen.getByTestId("email")).toHaveTextContent(testUser.email);
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBe("valid-token");
    expect(authApi.login).toHaveBeenCalledWith({ email: "ada@example.com", password: "secret" });
    expect(authApi.getAuthenticatedUser).toHaveBeenCalledOnce();
  });

  it("restores a valid stored session after browser refresh", async () => {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, "stored-token");
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);

    render(<AuthHarness />, { wrapper: TestProviders });

    expect(screen.getByTestId("initializing")).toHaveTextContent("true");
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(screen.getByTestId("email")).toHaveTextContent(testUser.email);
  });

  it("clears an invalid stored token", async () => {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, "invalid-token");
    vi.mocked(authApi.getAuthenticatedUser).mockRejectedValue(new Error("Unauthorized"));

    render(<AuthHarness />, { wrapper: TestProviders });

    await waitFor(() => expect(screen.getByTestId("initializing")).toHaveTextContent("false"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull();
  });

  it("clears token, user, and workspace on logout", async () => {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, "stored-token");
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    const user = userEvent.setup();
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
    expect(screen.getByTestId("workspace")).toHaveTextContent("none");
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull();
  });

  it("clears the session when the Axios 401 handler reports expiration", async () => {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, "stored-token");
    vi.mocked(authApi.getAuthenticatedUser).mockResolvedValue(testUser);
    render(<AuthHarness />, { wrapper: TestProviders });
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));

    await act(async () => handleUnauthorized());

    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull();
  });
});
