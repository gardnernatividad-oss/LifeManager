import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import { WorkspaceSelector } from "./WorkspaceSelector";

vi.mock("../../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const personal = { id: "11111111-1111-4111-8111-111111111111", name: "Personal", kind: "PERSONAL" as const, lifecycle: "ACTIVE" as const, visible_role: "Propietario" as const, can_manage: false, can_delete: false, timezone: "America/Lima" };
const shared = { ...personal, id: "22222222-2222-4222-8222-222222222222", name: "Familia", kind: "SHARED" as const, can_manage: true };

function mount() {
  const setWorkspace = vi.fn();
  const auth: AuthState = { user: testUser, workspace: personal, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace, clearSession: vi.fn(), setAuthenticatedUser: vi.fn() };
  vi.mocked(useAuth).mockReturnValue(auth);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><WorkspaceSelector /></QueryClientProvider>);
  return setWorkspace;
}

describe("WorkspaceSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([personal, shared]);
  });

  it("shows Personal first and switches using validated active listing data", async () => {
    const user = userEvent.setup();
    const setWorkspace = mount();
    const selector = await screen.findByRole("combobox", { name: "Espacio de trabajo activo" });
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["Personal · Personal", "Familia"]);
    await user.selectOptions(selector, shared.id);
    expect(setWorkspace).toHaveBeenCalledWith(shared);
    expect(window.localStorage.getItem("lifemanager.selected-workspace-id")).toBe(shared.id);
  });
});
