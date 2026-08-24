import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState, type PropsWithChildren } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as categoryApi from "../../api/categoryApi";
import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { WorkspaceSummary } from "../../types/auth";
import type { Category } from "../../types/category";
import { CategoriesPage } from "./CategoriesPage";

vi.mock("../../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../api/categoryApi", () => ({
  listCategories: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  activateCategory: vi.fn(),
  deactivateCategory: vi.fn()
}));

const workspaceOne: WorkspaceSummary = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  name: "Hogar",
  description: null,
  timezone: "America/Lima",
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z"
};

const workspaceTwo: WorkspaceSummary = {
  ...workspaceOne,
  id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  name: "Trabajo"
};

const activeCategory: Category = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: workspaceOne.id,
  name: "Personal",
  description: null,
  is_active: true,
  created_at: "2026-08-06T12:00:00Z",
  updated_at: "2026-08-06T12:00:00Z"
};

const inactiveCategory: Category = {
  ...activeCategory,
  id: "22222222-2222-4222-8222-222222222222",
  name: "Antigua",
  is_active: false
};

function WorkspaceSwitchButton() {
  const { setWorkspace } = useAuth();
  return <button type="button" onClick={() => setWorkspace(workspaceTwo)}>Cambiar espacio</button>;
}

function StatefulAuth({ children, initialWorkspace }: PropsWithChildren<{ initialWorkspace: WorkspaceSummary | null }>) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const value = useMemo<AuthState>(() => ({
    user: testUser,
    workspace,
    isAuthenticated: true,
    isInitializing: false,
    login: vi.fn(),
    logout: vi.fn(),
    setWorkspace,
    clearSession: vi.fn(),
    setAuthenticatedUser: vi.fn()
  }), [workspace]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function renderCategories(
  initialWorkspace: WorkspaceSummary | null = workspaceOne,
  includeSwitcher = false
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <StatefulAuth initialWorkspace={initialWorkspace}>
        <MemoryRouter initialEntries={["/settings/categories"]}>
          {includeSwitcher ? <WorkspaceSwitchButton /> : null}
          <CategoriesPage />
        </MemoryRouter>
      </StatefulAuth>
    </QueryClientProvider>
  );
  return queryClient;
}

describe("CategoriesPage", () => {
  beforeEach(() => {
    vi.mocked(workspaceApi.listWorkspaces).mockReset();
    vi.mocked(categoryApi.listCategories).mockReset();
    vi.mocked(categoryApi.createCategory).mockReset();
    vi.mocked(categoryApi.updateCategory).mockReset();
    vi.mocked(categoryApi.activateCategory).mockReset();
    vi.mocked(categoryApi.deactivateCategory).mockReset();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne]);
    vi.mocked(categoryApi.listCategories).mockResolvedValue([activeCategory, inactiveCategory]);
    vi.mocked(categoryApi.createCategory).mockResolvedValue(activeCategory);
    vi.mocked(categoryApi.updateCategory).mockResolvedValue(activeCategory);
    vi.mocked(categoryApi.activateCategory).mockResolvedValue({ ...inactiveCategory, is_active: true });
    vi.mocked(categoryApi.deactivateCategory).mockResolvedValue({ ...activeCategory, is_active: false });
  });

  it("loads Categories for the selected Workspace and omits the all-filter parameter", async () => {
    renderCategories();

    expect(await screen.findByText("Personal")).toBeInTheDocument();
    expect(screen.getByText("Antigua")).toBeInTheDocument();
    expect(categoryApi.listCategories).toHaveBeenCalledWith(workspaceOne.id, null);
  });

  it("does not call Categories without an available Workspace", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([]);
    renderCategories(null);

    expect(await screen.findByText("No hay un espacio de trabajo disponible")).toBeInTheDocument();
    expect(categoryApi.listCategories).not.toHaveBeenCalled();
  });

  it("isolates Category queries when the Workspace changes", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne, workspaceTwo]);
    const user = userEvent.setup();
    const queryClient = renderCategories(workspaceOne, true);
    await screen.findByText("Personal");

    await user.click(screen.getByRole("button", { name: "Cambiar espacio" }));

    await waitFor(() => expect(categoryApi.listCategories).toHaveBeenCalledWith(workspaceTwo.id, null));
    expect(queryClient.getQueryData(["categories", workspaceOne.id, null])).toEqual([
      activeCategory,
      inactiveCategory
    ]);
    expect(queryClient.getQueryData(["categories", workspaceTwo.id, null])).toBeDefined();
  });

  it("renders loading, empty, and list failure states with retry", async () => {
    vi.mocked(categoryApi.listCategories).mockReturnValueOnce(new Promise(() => undefined));
    const firstRender = renderCategories();
    expect(await screen.findByRole("status", { name: "Cargando categorías" })).toBeInTheDocument();
    firstRender.clear();

    vi.mocked(categoryApi.listCategories).mockResolvedValueOnce([]);
    renderCategories();
    expect(await screen.findByText("Aún no tienes categorías.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear primera categoría" })).toBeInTheDocument();
  });

  it("renders list failure and retries", async () => {
    vi.mocked(categoryApi.listCategories)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([activeCategory]);
    const user = userEvent.setup();
    renderCategories();

    expect(await screen.findByText("No pudimos cargar las categorías.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Personal")).toBeInTheDocument();
    expect(categoryApi.listCategories).toHaveBeenCalledTimes(2);
  });

  it("maps active and inactive filters exactly to the backend contract", async () => {
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");

    await user.click(screen.getByRole("button", { name: "Activas" }));
    await waitFor(() => expect(categoryApi.listCategories).toHaveBeenCalledWith(workspaceOne.id, true));
    await user.click(screen.getByRole("button", { name: "Inactivas" }));
    await waitFor(() => expect(categoryApi.listCategories).toHaveBeenCalledWith(workspaceOne.id, false));
    await user.click(screen.getByRole("button", { name: "Todas" }));
    expect(categoryApi.listCategories).toHaveBeenCalledWith(workspaceOne.id, null);
  });

  it("validates and creates a Category, then invalidates only its Workspace", async () => {
    const user = userEvent.setup();
    const queryClient = renderCategories();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText("Personal");
    await user.click(screen.getByRole("button", { name: "Nueva categoría" }));
    await user.click(screen.getByRole("button", { name: "Guardar categoría" }));
    expect(await screen.findByText("Ingresa un nombre.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Nombre"), "  Trabajo  ");
    await user.click(screen.getByRole("button", { name: "Guardar categoría" }));

    await waitFor(() => expect(categoryApi.createCategory).toHaveBeenCalledWith(
      workspaceOne.id,
      { name: "Trabajo" }
    ));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["categories", workspaceOne.id] });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["categories", workspaceTwo.id] });
    expect(await screen.findByText("Categoría creada.")).toBeInTheDocument();
  });

  it("preserves the create value and shows a Spanish duplicate-name conflict", async () => {
    vi.mocked(categoryApi.createCategory).mockRejectedValue({
      isAxiosError: true,
      response: { status: 409 }
    });
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");
    await user.click(screen.getByRole("button", { name: "Nueva categoría" }));
    await user.type(screen.getByLabelText("Nombre"), "Personal");
    await user.click(screen.getByRole("button", { name: "Guardar categoría" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe una categoría con ese nombre en este espacio."
    );
    expect(screen.getByLabelText("Nombre")).toHaveValue("Personal");
  });

  it("prefills and successfully edits only the Category name", async () => {
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");
    await user.click(screen.getByRole("button", { name: "Editar Personal" }));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Personal");

    await user.clear(screen.getByLabelText("Nombre"));
    await user.type(screen.getByLabelText("Nombre"), "Familia");
    await user.click(screen.getByRole("button", { name: "Guardar categoría" }));

    await waitFor(() => expect(categoryApi.updateCategory).toHaveBeenCalledWith(
      workspaceOne.id,
      activeCategory.id,
      { name: "Familia" }
    ));
    expect(categoryApi.activateCategory).not.toHaveBeenCalled();
    expect(categoryApi.deactivateCategory).not.toHaveBeenCalled();
  });

  it("handles duplicate-name conflicts while editing", async () => {
    vi.mocked(categoryApi.updateCategory).mockRejectedValue({
      isAxiosError: true,
      response: { status: 409 }
    });
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");
    await user.click(screen.getByRole("button", { name: "Editar Personal" }));
    await user.click(screen.getByRole("button", { name: "Guardar categoría" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe una categoría con ese nombre en este espacio."
    );
  });

  it("deactivates active Categories and activates inactive Categories", async () => {
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");

    await user.click(screen.getByRole("button", { name: "Desactivar Personal" }));
    await waitFor(() => expect(categoryApi.deactivateCategory).toHaveBeenCalledWith(
      workspaceOne.id,
      activeCategory.id
    ));
    await user.click(screen.getByRole("button", { name: "Activar Antigua" }));
    await waitFor(() => expect(categoryApi.activateCategory).toHaveBeenCalledWith(
      workspaceOne.id,
      inactiveCategory.id
    ));
  });

  it("disables the lifecycle action while it is pending", async () => {
    vi.mocked(categoryApi.deactivateCategory).mockReturnValue(new Promise(() => undefined));
    const user = userEvent.setup();
    renderCategories();
    await screen.findByText("Personal");

    await user.click(screen.getByRole("button", { name: "Desactivar Personal" }));

    expect(screen.getByRole("button", { name: "Actualizando…" })).toBeDisabled();
  });
});
