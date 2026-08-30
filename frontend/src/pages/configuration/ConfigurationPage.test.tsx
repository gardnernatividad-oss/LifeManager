import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../../api/authApi";
import * as workspaceApi from "../../api/workspaceApi";
import * as notificationApi from "../../api/v2NotificationApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import { ConfigurationPage } from "./ConfigurationPage";

vi.mock("../../api/authApi", () => ({ listTimezones: vi.fn(), updateAuthenticatedUser: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({
  listManagedWorkspaces: vi.fn(), listMyWorkspaceInvitations: vi.fn(),
  listWorkspaceMembers: vi.fn(), listWorkspaceInvitations: vi.fn(),
  createSharedWorkspace: vi.fn(), createWorkspaceInvitation: vi.fn(),
  actOnWorkspaceInvitation: vi.fn(), deactivateWorkspace: vi.fn(),
  reactivateWorkspace: vi.fn(), deleteWorkspace: vi.fn(), leaveWorkspace: vi.fn(),
  removeWorkspaceMember: vi.fn(), transferWorkspaceOwnership: vi.fn(),
}));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("../../api/v2NotificationApi", () => ({ getNotificationPreferences: vi.fn(), updateNotificationPreferences: vi.fn() }));

const notificationPreferences = { daily_summary: { enabled: true, local_time: "07:00:00", weekday: null, lock_version: 1 }, daily_review: { enabled: true, local_time: "21:00:00", weekday: null, lock_version: 1 }, pending_weekly: { enabled: true, local_time: "22:00:00", weekday: 6, lock_version: 1 }, project_weekly: { enabled: true, local_time: "22:30:00", weekday: 6, lock_version: 1 }, activity_reminders: { enabled: true, lock_version: 1 } };

const setAuthenticatedUser = vi.fn();
function auth(): AuthState {
  return { user: testUser, workspace: null, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser };
}
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><ConfigurationPage /></QueryClientProvider>);
  return invalidate;
}

describe("ConfigurationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue(auth());
    vi.mocked(authApi.listTimezones).mockResolvedValue(["America/Lima", "Europe/London"]);
    vi.mocked(workspaceApi.listManagedWorkspaces).mockResolvedValue([]);
    vi.mocked(workspaceApi.listMyWorkspaceInvitations).mockResolvedValue([]);
    vi.mocked(notificationApi.getNotificationPreferences).mockResolvedValue(notificationPreferences);
    vi.mocked(notificationApi.updateNotificationPreferences).mockResolvedValue(notificationPreferences);
  });

  it("shows only editable names/timezone and read-only email", async () => {
    mount();
    expect(screen.getByLabelText("Correo electrónico")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Nombre")).toHaveValue(testUser.first_name);
    expect(screen.getByLabelText("Apellido")).toHaveValue(testUser.last_name);
    expect(await screen.findByLabelText("Zona horaria")).toHaveValue(testUser.timezone);
    expect(screen.getAllByRole("button", { name: "Guardar" })).toHaveLength(1);
  });

  it("loads timezone options and retries safely", async () => {
    vi.mocked(authApi.listTimezones).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(["America/Lima"]);
    const user = userEvent.setup(); mount();
    expect(await screen.findByText("No pudimos cargar las zonas horarias.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("option", { name: "America/Lima" })).toBeInTheDocument();
  });

  it("saves exact profile fields, refreshes auth and invalidates Home/Review", async () => {
    const saved = { ...testUser, first_name: "Augusta", last_name: "King", timezone: "Europe/London" };
    vi.mocked(authApi.updateAuthenticatedUser).mockResolvedValue(saved);
    const user = userEvent.setup(); const invalidate = mount();
    await screen.findByRole("option", { name: "Europe/London" });
    await user.clear(screen.getByLabelText("Nombre")); await user.type(screen.getByLabelText("Nombre"), "Augusta");
    await user.clear(screen.getByLabelText("Apellido")); await user.type(screen.getByLabelText("Apellido"), "King");
    await user.selectOptions(screen.getByLabelText("Zona horaria"), "Europe/London");
    expect(authApi.updateAuthenticatedUser).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(authApi.updateAuthenticatedUser).toHaveBeenCalledWith({ first_name: "Augusta", last_name: "King", timezone: "Europe/London" }));
    expect(setAuthenticatedUser).toHaveBeenCalledWith(saved);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.home });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.review });
    for (const key of [
      queryKeys.planningTasksRoot,
      queryKeys.trackingTasksRoot,
      queryKeys.planningPendingItemsRoot,
      queryKeys.trackingPendingItemsRoot,
      queryKeys.planningProjectsRoot,
      queryKeys.trackingProjectsRoot,
      queryKeys.pendingItemReportsRoot,
      queryKeys.projectReportsRoot,
    ]) expect(invalidate).toHaveBeenCalledWith({ queryKey: key });
    expect(await screen.findByRole("status")).toHaveTextContent("Configuración guardada.");
  });
});
