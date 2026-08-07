import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState, type PropsWithChildren } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as projectApi from "../../api/projectApi";
import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { WorkspaceSummary } from "../../types/auth";
import type { Project } from "../../types/project";
import { ProjectsPage } from "./ProjectsPage";

vi.mock("../../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../api/projectApi", () => ({
  listProjects: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  activateProject: vi.fn(),
  deactivateProject: vi.fn()
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

const activeProject: Project = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: workspaceOne.id,
  name: "Casa",
  description: "Organización del proyecto personal",
  is_active: true,
  created_at: "2026-08-06T12:00:00Z",
  updated_at: "2026-08-06T12:00:00Z"
};

const inactiveProject: Project = {
  ...activeProject,
  id: "22222222-2222-4222-8222-222222222222",
  name: "Proyecto anterior",
  description: null,
  is_active: false
};

function WorkspaceSwitchButton() {
  const { setWorkspace } = useAuth();
  return <button type="button" onClick={() => setWorkspace(workspaceTwo)}>Cambiar espacio</button>;
}

function StatefulAuth({ children, initialWorkspace }: PropsWithChildren<{ initialWorkspace: WorkspaceSummary | null }>) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const value = useMemo<AuthState>(() => ({
    accessToken: "token",
    user: testUser,
    workspace,
    isAuthenticated: true,
    isInitializing: false,
    login: vi.fn(),
    logout: vi.fn(),
    setWorkspace,
    clearSession: vi.fn()
  }), [workspace]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function renderProjects(initialWorkspace: WorkspaceSummary | null = workspaceOne, includeSwitcher = false) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <StatefulAuth initialWorkspace={initialWorkspace}>
        <MemoryRouter initialEntries={["/projects"]}>
          {includeSwitcher ? <WorkspaceSwitchButton /> : null}
          <ProjectsPage />
        </MemoryRouter>
      </StatefulAuth>
    </QueryClientProvider>
  );
  return queryClient;
}

describe("ProjectsPage", () => {
  beforeEach(() => {
    vi.mocked(workspaceApi.listWorkspaces).mockReset();
    vi.mocked(projectApi.listProjects).mockReset();
    vi.mocked(projectApi.createProject).mockReset();
    vi.mocked(projectApi.updateProject).mockReset();
    vi.mocked(projectApi.activateProject).mockReset();
    vi.mocked(projectApi.deactivateProject).mockReset();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne]);
    vi.mocked(projectApi.listProjects).mockResolvedValue([activeProject, inactiveProject]);
    vi.mocked(projectApi.createProject).mockResolvedValue(activeProject);
    vi.mocked(projectApi.updateProject).mockResolvedValue(activeProject);
    vi.mocked(projectApi.activateProject).mockResolvedValue({ ...inactiveProject, is_active: true });
    vi.mocked(projectApi.deactivateProject).mockResolvedValue({ ...activeProject, is_active: false });
  });

  it("loads Projects for the selected Workspace with descriptions and no all-filter", async () => {
    renderProjects();
    expect(await screen.findByText("Casa")).toBeInTheDocument();
    expect(screen.getByText("Organización del proyecto personal")).toBeInTheDocument();
    expect(screen.getByText("Sin descripción")).toBeInTheDocument();
    expect(projectApi.listProjects).toHaveBeenCalledWith(workspaceOne.id, null);
  });

  it("does not call Projects without an available Workspace", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([]);
    renderProjects(null);
    expect(await screen.findByText("No hay un espacio de trabajo disponible")).toBeInTheDocument();
    expect(projectApi.listProjects).not.toHaveBeenCalled();
  });

  it("isolates Project queries when the Workspace changes", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne, workspaceTwo]);
    const user = userEvent.setup();
    const queryClient = renderProjects(workspaceOne, true);
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Cambiar espacio" }));
    await waitFor(() => expect(projectApi.listProjects).toHaveBeenCalledWith(workspaceTwo.id, null));
    expect(queryClient.getQueryData(["projects", workspaceOne.id, null])).toEqual([
      activeProject,
      inactiveProject
    ]);
    expect(queryClient.getQueryData(["projects", workspaceTwo.id, null])).toBeDefined();
  });

  it("renders a loading state before Project data is available", async () => {
    vi.mocked(projectApi.listProjects).mockReturnValue(new Promise(() => undefined));
    renderProjects();
    expect(await screen.findByRole("status", { name: "Cargando proyectos" })).toBeInTheDocument();
    expect(screen.queryByText("Aún no tienes proyectos.")).not.toBeInTheDocument();
  });

  it("renders a useful empty state", async () => {
    vi.mocked(projectApi.listProjects).mockResolvedValue([]);
    renderProjects();
    expect(await screen.findByText("Aún no tienes proyectos.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear primer proyecto" })).toBeInTheDocument();
  });

  it("renders list failure and retries", async () => {
    vi.mocked(projectApi.listProjects)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([activeProject]);
    const user = userEvent.setup();
    renderProjects();
    expect(await screen.findByText("No pudimos cargar los proyectos.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Casa")).toBeInTheDocument();
    expect(projectApi.listProjects).toHaveBeenCalledTimes(2);
  });

  it("maps all active-state filters to the backend contract", async () => {
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Activos" }));
    await waitFor(() => expect(projectApi.listProjects).toHaveBeenCalledWith(workspaceOne.id, true));
    await user.click(screen.getByRole("button", { name: "Inactivos" }));
    await waitFor(() => expect(projectApi.listProjects).toHaveBeenCalledWith(workspaceOne.id, false));
    await user.click(screen.getByRole("button", { name: "Todos" }));
    expect(projectApi.listProjects).toHaveBeenCalledWith(workspaceOne.id, null);
  });

  it("validates and creates a Project while invalidating only its Workspace", async () => {
    const user = userEvent.setup();
    const queryClient = renderProjects();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Nuevo proyecto" }));
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    expect(await screen.findByText("Ingresa un nombre.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Nombre"), "  Jardín  ");
    await user.type(screen.getByLabelText(/Descripción/), "  Renovación exterior  ");
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    await waitFor(() => expect(projectApi.createProject).toHaveBeenCalledWith(
      workspaceOne.id,
      { name: "Jardín", description: "Renovación exterior" }
    ));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", workspaceOne.id] });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["projects", workspaceTwo.id] });
    expect(await screen.findByText("Proyecto creado.")).toBeInTheDocument();
  });

  it("submits an empty optional description as null", async () => {
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Nuevo proyecto" }));
    await user.type(screen.getByLabelText("Nombre"), "Proyecto simple");
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    await waitFor(() => expect(projectApi.createProject).toHaveBeenCalledWith(
      workspaceOne.id,
      { name: "Proyecto simple", description: null }
    ));
  });

  it("preserves create values and translates duplicate-name conflicts", async () => {
    vi.mocked(projectApi.createProject).mockRejectedValue({
      isAxiosError: true,
      response: { status: 409 }
    });
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Nuevo proyecto" }));
    await user.type(screen.getByLabelText("Nombre"), "Casa");
    await user.type(screen.getByLabelText(/Descripción/), "Texto conservado");
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe un proyecto con ese nombre en este espacio."
    );
    expect(screen.getByLabelText("Nombre")).toHaveValue("Casa");
    expect(screen.getByLabelText(/Descripción/)).toHaveValue("Texto conservado");
  });

  it("prefills and successfully edits name and description without changing lifecycle", async () => {
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Editar Casa" }));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Casa");
    expect(screen.getByLabelText(/Descripción/)).toHaveValue(activeProject.description);
    await user.clear(screen.getByLabelText("Nombre"));
    await user.type(screen.getByLabelText("Nombre"), "Casa renovada");
    await user.clear(screen.getByLabelText(/Descripción/));
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    await waitFor(() => expect(projectApi.updateProject).toHaveBeenCalledWith(
      workspaceOne.id,
      activeProject.id,
      { name: "Casa renovada", description: null }
    ));
    expect(projectApi.activateProject).not.toHaveBeenCalled();
    expect(projectApi.deactivateProject).not.toHaveBeenCalled();
  });

  it("translates duplicate-name conflicts while editing", async () => {
    vi.mocked(projectApi.updateProject).mockRejectedValue({
      isAxiosError: true,
      response: { status: 409 }
    });
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Editar Casa" }));
    await user.click(screen.getByRole("button", { name: "Guardar proyecto" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe un proyecto con ese nombre en este espacio."
    );
  });

  it("deactivates active Projects and activates inactive Projects", async () => {
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Desactivar Casa" }));
    await waitFor(() => expect(projectApi.deactivateProject).toHaveBeenCalledWith(
      workspaceOne.id,
      activeProject.id
    ));
    await user.click(screen.getByRole("button", { name: "Activar Proyecto anterior" }));
    await waitFor(() => expect(projectApi.activateProject).toHaveBeenCalledWith(
      workspaceOne.id,
      inactiveProject.id
    ));
  });

  it("disables the lifecycle action while pending", async () => {
    vi.mocked(projectApi.deactivateProject).mockReturnValue(new Promise(() => undefined));
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Desactivar Casa" }));
    expect(screen.getByRole("button", { name: "Actualizando…" })).toBeDisabled();
  });

  it("shows a friendly lifecycle failure without exposing backend details", async () => {
    vi.mocked(projectApi.deactivateProject).mockRejectedValue(new Error("database detail"));
    const user = userEvent.setup();
    renderProjects();
    await screen.findByText("Casa");
    await user.click(screen.getByRole("button", { name: "Desactivar Casa" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos cambiar el estado del proyecto. Intenta nuevamente."
    );
    expect(screen.queryByText("database detail")).not.toBeInTheDocument();
  });
});
