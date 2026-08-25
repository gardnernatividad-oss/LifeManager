import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { AuthenticatedUser } from "../../types/auth";
import { WorkspaceManagement } from "./WorkspaceManagement";

vi.mock("../../api/workspaceApi", () => ({
  listManagedWorkspaces: vi.fn(), listMyWorkspaceInvitations: vi.fn(),
  listWorkspaceMembers: vi.fn(), listWorkspaceInvitations: vi.fn(),
  createSharedWorkspace: vi.fn(), createWorkspaceInvitation: vi.fn(),
  actOnWorkspaceInvitation: vi.fn(), deactivateWorkspace: vi.fn(), reactivateWorkspace: vi.fn(),
  deleteWorkspace: vi.fn(), leaveWorkspace: vi.fn(), removeWorkspaceMember: vi.fn(),
  transferWorkspaceOwnership: vi.fn(),
}));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const personal = { id: "11111111-1111-4111-8111-111111111111", name: "Personal", kind: "PERSONAL" as const, lifecycle: "ACTIVE" as const, visible_role: "Propietario" as const, can_manage: false, can_delete: false, timezone: "America/Lima" };
const shared = { ...personal, id: "22222222-2222-4222-8222-222222222222", name: "Familia", kind: "SHARED" as const, can_manage: true };
const inactive = { ...shared, id: "33333333-3333-4333-8333-333333333333", name: "Archivo", lifecycle: "INACTIVE" as const };
const member = { user_id: "44444444-4444-4444-8444-444444444444", display_name: "Luis Pérez", email: "luis@example.com", role: "Miembro" as const, status: "ACTIVE" as const, joined_at: "2026-08-24T12:00:00Z", ended_at: null };

function mount(user: AuthenticatedUser = testUser) {
  const state: AuthState = { user, workspace: personal, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn() };
  vi.mocked(useAuth).mockReturnValue(state);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><WorkspaceManagement /></QueryClientProvider>);
}

describe("WorkspaceManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listManagedWorkspaces).mockResolvedValue([personal, shared, inactive]);
    vi.mocked(api.listMyWorkspaceInvitations).mockResolvedValue([]);
    vi.mocked(api.listWorkspaceMembers).mockResolvedValue([{ ...member, user_id: testUser.id, display_name: "Ada Lovelace", email: testUser.email, role: "Propietario" }, member]);
    vi.mocked(api.listWorkspaceInvitations).mockResolvedValue([]);
    vi.mocked(api.reactivateWorkspace).mockResolvedValue({ ...inactive, lifecycle: "ACTIVE" });
    vi.mocked(api.deactivateWorkspace).mockResolvedValue({ ...shared, lifecycle: "INACTIVE" });
  });

  it("separates active/inactive Workspaces and exposes owner reactivation only", async () => {
    const user = userEvent.setup();
    mount();
    expect(screen.getByRole("heading", { name: "Activos" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inactivos" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Archivo/ }));
    await user.click(screen.getByRole("button", { name: "Reactivar Workspace" }));
    await waitFor(() => expect(api.reactivateWorkspace).toHaveBeenCalledWith(inactive.id));
  });

  it("integrates member, ownership and invitation controls for an active owner", async () => {
    const user = userEvent.setup();
    vi.mocked(api.transferWorkspaceOwnership).mockResolvedValue(shared);
    vi.mocked(api.createWorkspaceInvitation).mockResolvedValue({ id: "55555555-5555-4555-8555-555555555555", workspace_id: shared.id, workspace_name: shared.name, recipient_email: "new@example.com", status: "PENDING", expires_at: "2026-09-01T00:00:00Z", created_at: "2026-08-24T00:00:00Z" });
    mount();
    await user.click(await screen.findByRole("button", { name: /Familia/ }));
    expect((await screen.findAllByText("Luis Pérez")).length).toBeGreaterThan(0);
    await user.type(screen.getByLabelText("Invitar por correo"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Invitar" }));
    await waitFor(() => expect(api.createWorkspaceInvitation).toHaveBeenCalledWith(shared.id, "new@example.com"));
    await user.selectOptions(screen.getByLabelText("Nuevo propietario"), member.user_id);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Transferir propiedad" }));
    expect(api.transferWorkspaceOwnership).toHaveBeenCalledWith(shared.id, member.user_id);
  });

  it("creates a Shared Workspace without allowing lifecycle or ownership fields", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createSharedWorkspace).mockResolvedValue(shared);
    mount();
    await user.type(await screen.findByLabelText("Nuevo espacio compartido"), "Familia");
    await user.click(screen.getByRole("button", { name: "Crear" }));
    await waitFor(() => expect(api.createSharedWorkspace).toHaveBeenCalledWith("Familia"));
  });

  it("derives member actions from Workspace role and gives GLOBAL_ADMIN no owner UI", async () => {
    const user = userEvent.setup();
    const memberWorkspace = { ...shared, visible_role: "Miembro" as const, can_manage: false };
    vi.mocked(api.listManagedWorkspaces).mockResolvedValue([personal, memberWorkspace]);
    mount({ ...testUser, global_role: "GLOBAL_ADMIN" });

    await user.click(await screen.findByRole("button", { name: /Familia/ }));
    expect(await screen.findByRole("button", { name: "Salir del Workspace" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Transferir propiedad" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Desactivar Workspace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Eliminar Workspace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invitar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retirar" })).not.toBeInTheDocument();
  });

  it("exposes no Shared lifecycle or collaboration actions for Personal", async () => {
    const user = userEvent.setup();
    mount();

    await user.click(await screen.findByRole("button", { name: /Personal/ }));
    expect(screen.getByText(/no admite transferencia, salida, desactivación ni eliminación/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Transferir propiedad" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salir del Workspace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invitar" })).not.toBeInTheDocument();
  });
});
