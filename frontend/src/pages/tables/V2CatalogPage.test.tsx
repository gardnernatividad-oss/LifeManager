import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/v2CatalogApi";
import { AuthContext } from "../../store/auth-context";
import type { AuthState } from "../../store/auth-context";
import { V2CatalogPage } from "./V2CatalogPage";

vi.mock("../../api/v2CatalogApi", () => ({
  listV2Catalog: vi.fn(), createV2Catalog: vi.fn(), updateV2Catalog: vi.fn(), setV2CatalogActive: vi.fn()
}));

const workspace = { id: "11111111-1111-4111-8111-111111111111", name: "Familia", timezone: "America/Lima" };
const category = { id: "22222222-2222-4222-8222-222222222222", workspace_id: workspace.id, name: "Personal", is_active: true, lock_version: 1, created_at: "2026-08-25T00:00:00Z", updated_at: "2026-08-25T00:00:00Z" };

function renderPage(node: React.ReactNode, selected = workspace) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const auth = { workspace: selected, user: { id: "u", email: "ana@example.com", first_name: "Ana", last_name: "Pérez", timezone: "America/Lima" }, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn() } satisfies AuthState;
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={auth}>{node}</AuthContext.Provider></QueryClientProvider>);
}

describe("V2CatalogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listV2Catalog).mockResolvedValue({ items: [category], total: 1 });
    vi.mocked(api.createV2Catalog).mockResolvedValue(category);
    vi.mocked(api.setV2CatalogActive).mockResolvedValue({ ...category, is_active: false, lock_version: 2 });
  });

  it("scopes Category queries and creation to the selected Workspace", async () => {
    const user = userEvent.setup();
    renderPage(<V2CatalogPage kind="categories" label="Categorías" singular="Categoría" />);
    expect(await screen.findByText("Personal")).toBeInTheDocument();
    expect(api.listV2Catalog).toHaveBeenCalledWith(workspace.id, "categories", expect.any(Object));
    await user.type(screen.getByLabelText("Nombre"), "Casa");
    await user.click(screen.getByRole("button", { name: "Crear" }));
    await waitFor(() => expect(api.createV2Catalog).toHaveBeenCalledWith(workspace.id, "categories", { name: "Casa" }));
  });

  it("shows the active lifecycle and uses a dedicated lifecycle operation", async () => {
    const user = userEvent.setup();
    renderPage(<V2CatalogPage kind="categories" label="Categorías" singular="Categoría" />);
    await user.click(await screen.findByRole("button", { name: "Desactivar" }));
    expect(api.setV2CatalogActive).toHaveBeenCalledWith(workspace.id, "categories", category, false);
  });

  it("does not query or leak catalog data without a selected Workspace", () => {
    renderPage(<V2CatalogPage kind="categories" label="Categorías" singular="Categoría" />, null as never);
    expect(screen.getByText("Selecciona un espacio de trabajo.")).toBeInTheDocument();
    expect(api.listV2Catalog).not.toHaveBeenCalled();
  });

  it("uses approved user-facing names", async () => {
    renderPage(<V2CatalogPage kind="activity-masters" label="Actividades" singular="Actividad" />);
    expect(await screen.findByRole("heading", { name: "Actividades" })).toBeInTheDocument();
    expect(screen.queryByText(/ActivityMaster|Tarea maestra/i)).not.toBeInTheDocument();
  });
});
