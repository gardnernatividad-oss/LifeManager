import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as workspaceApi from "../api/workspaceApi";
import type { AuthState } from "../store/auth-context";
import { AuthContext } from "../store/auth-context";
import { testUser } from "../test/testUser";
import type { WorkspaceSummary } from "../types/auth";
import { useWorkspaces } from "./useWorkspaces";

vi.mock("../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));

const personal: WorkspaceSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Personal",
  kind: "PERSONAL",
  lifecycle: "ACTIVE",
  visible_role: "Propietario",
  can_manage: false,
  can_delete: false,
  timezone: "America/Lima",
};

function Harness() {
  useWorkspaces();
  return null;
}

function mount(workspace: WorkspaceSummary | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const setWorkspace = vi.fn();
  const auth: AuthState = {
    user: testUser,
    workspace,
    isAuthenticated: true,
    isInitializing: false,
    login: vi.fn(),
    logout: vi.fn(),
    setWorkspace,
    clearSession: vi.fn(),
    setAuthenticatedUser: vi.fn(),
  };
  function Providers({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}><AuthContext.Provider value={auth}>{children}</AuthContext.Provider></QueryClientProvider>;
  }
  render(<Harness />, { wrapper: Providers });
  return { client, setWorkspace };
}

describe("useWorkspaces isolation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([personal]);
  });

  it("rejects an inaccessible stored selection and falls back to Personal", async () => {
    window.localStorage.setItem("lifemanager.selected-workspace-id", "99999999-9999-4999-8999-999999999999");
    const { setWorkspace } = mount(null);

    await waitFor(() => expect(setWorkspace).toHaveBeenCalledWith(personal));
    expect(window.localStorage.getItem("lifemanager.selected-workspace-id")).toBe(personal.id);
  });

  it("falls back when the selected Workspace loses access and clears scoped cache only", async () => {
    const unavailable = { ...personal, id: "22222222-2222-4222-8222-222222222222", kind: "SHARED" as const };
    const { client, setWorkspace } = mount(unavailable);
    client.setQueryData(["tasks", unavailable.id], { private: true });
    client.setQueryData(["home"], { global: true });
    client.setQueryData(["review"], { global: true });

    await waitFor(() => expect(setWorkspace).toHaveBeenCalledWith(personal));
    expect(client.getQueryData(["tasks", unavailable.id])).toBeUndefined();
    expect(client.getQueryData(["home"])).toEqual({ global: true });
    expect(client.getQueryData(["review"])).toEqual({ global: true });
  });
});
