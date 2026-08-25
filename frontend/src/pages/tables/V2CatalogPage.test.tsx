import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/v2CatalogApi";
import { AuthContext } from "../../store/auth-context";
import type { AuthState } from "../../store/auth-context";
import { V2CatalogPage } from "./V2CatalogPage";

vi.mock("../../api/v2CatalogApi", () => ({
  listV2Catalog: vi.fn(), listV2CatalogSelector: vi.fn(), createV2Catalog: vi.fn(), updateV2Catalog: vi.fn(), setV2CatalogActive: vi.fn(), deleteV2Catalog: vi.fn()
}));

const workspace = { id: "11111111-1111-4111-8111-111111111111", name: "Familia", timezone: "America/Lima" };
const category = { id: "22222222-2222-4222-8222-222222222222", workspace_id: workspace.id, name: "Personal", is_active: true, lock_version: 1, can_delete: false, created_at: "2026-08-25T00:00:00Z", updated_at: "2026-08-25T00:00:00Z" };

function renderPage(node: React.ReactNode, selected = workspace) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const auth = { workspace: selected, user: { id: "u", email: "ana@example.com", first_name: "Ana", last_name: "Pérez", timezone: "America/Lima" }, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn() } satisfies AuthState;
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={auth}>{node}</AuthContext.Provider></QueryClientProvider>);
}

describe("V2CatalogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listV2Catalog).mockResolvedValue({ items: [category], total: 1 });
    vi.mocked(api.listV2CatalogSelector).mockResolvedValue([{ id: category.id, name: category.name, is_active: true, category_id: null, category_name: null }]);
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

  it("shows server-derived delete only for an unused item", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.listV2Catalog).mockResolvedValue({ items: [{ ...category, can_delete: true }], total: 1 });
    vi.mocked(api.deleteV2Catalog).mockResolvedValue();
    renderPage(<V2CatalogPage kind="categories" label="Categorías" singular="Categoría" />);
    await user.click(await screen.findByRole("button", { name: "Eliminar" }));
    expect(api.deleteV2Catalog).toHaveBeenCalledWith(workspace.id, "categories", expect.objectContaining({ can_delete: true }));
    expect(screen.getByRole("button", { name: "Desactivar" })).toBeInTheDocument();
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

  it("preserves a current inactive Category when editing only the item name", async () => {
    const user = userEvent.setup();
    const item = { ...category, id: "33333333-3333-4333-8333-333333333333", category_id: category.id, category_name: category.name, name: "Leer" };
    vi.mocked(api.listV2Catalog).mockResolvedValue({ items: [item], total: 1 });
    vi.mocked(api.listV2CatalogSelector).mockResolvedValue([{ id: category.id, name: category.name, is_active: false, category_id: null, category_name: null }]);
    vi.mocked(api.updateV2Catalog).mockResolvedValue({ ...item, name: "Leer diario", lock_version: 2 });

    renderPage(<V2CatalogPage kind="master-tasks" label="Tareas" singular="Tarea" />);
    await user.click(await screen.findByRole("button", { name: "Editar Tarea Leer" }));
    expect(await screen.findAllByRole("option", { name: "Personal (Inactiva)" })).toHaveLength(2);
    const name = screen.getByLabelText("Nombre de Tarea Leer");
    await user.clear(name);
    await user.type(name, "Leer diario");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(api.updateV2Catalog).toHaveBeenCalledWith(workspace.id, "master-tasks", item.id, { name: "Leer diario", lock_version: 1 }));
  });

  it("drops editor state and catalog data when the selected Workspace changes", async () => {
    const user = userEvent.setup();
    const secondWorkspace = { ...workspace, id: "44444444-4444-4444-8444-444444444444", name: "Trabajo" };
    const secondCategory = { ...category, id: "55555555-5555-4555-8555-555555555555", workspace_id: secondWorkspace.id, name: "Laboral" };
    vi.mocked(api.listV2Catalog).mockImplementation(async (workspaceId) => ({ items: [workspaceId === workspace.id ? category : secondCategory], total: 1 }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const auth = (selected: typeof workspace) => ({ workspace: selected, user: { id: "u", email: "ana@example.com", first_name: "Ana", last_name: "Pérez", timezone: "America/Lima" }, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn() } satisfies AuthState);
    const node = (selected: typeof workspace) => <QueryClientProvider client={client}><AuthContext.Provider value={auth(selected)}><V2CatalogPage kind="categories" label="Categorías" singular="Categoría" /></AuthContext.Provider></QueryClientProvider>;
    const view = render(node(workspace));

    await user.click(await screen.findByRole("button", { name: "Editar Categoría Personal" }));
    expect(screen.getByLabelText("Nombre de Categoría Personal")).toBeInTheDocument();
    view.rerender(node(secondWorkspace));

    expect(await screen.findByText("Laboral")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nombre de Categoría Personal")).not.toBeInTheDocument();
    expect(api.listV2Catalog).toHaveBeenCalledWith(secondWorkspace.id, "categories", expect.any(Object));
  });
});
