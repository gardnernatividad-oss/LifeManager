import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../../api/authApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import { ConfigurationPage } from "./ConfigurationPage";

vi.mock("../../api/authApi", () => ({ listTimezones: vi.fn(), updateAuthenticatedUser: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

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
  });

  it("shows only editable names/timezone and read-only email", async () => {
    mount();
    expect(screen.getByLabelText("Correo electrónico")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Nombre")).toHaveValue(testUser.first_name);
    expect(screen.getByLabelText("Apellido")).toHaveValue(testUser.last_name);
    expect(await screen.findByLabelText("Zona horaria")).toHaveValue(testUser.timezone);
    expect(screen.getAllByRole("button", { name: "Guardar" })).toHaveLength(1);
    expect(screen.queryByLabelText(/semana|contraseña|idioma|recordatorio|notificación|workspace|espacio/i)).not.toBeInTheDocument();
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
