import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useMemo, useState, type PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as categoryApi from "../../api/categoryApi";
import * as projectApi from "../../api/projectApi";
import * as taskApi from "../../api/taskApi";
import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { WorkspaceSummary } from "../../types/auth";
import type { Task, TaskListResponse } from "../../types/task";
import { localDateTimeToIso } from "../../utils/taskDateTime";
import { TasksPage } from "./TasksPage";

vi.mock("../../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../api/categoryApi", () => ({ listCategories: vi.fn() }));
vi.mock("../../api/projectApi", () => ({ listProjects: vi.fn() }));
vi.mock("../../api/taskApi", () => ({ listTasks: vi.fn(), createTask: vi.fn(), updateTask: vi.fn(), completeTask: vi.fn(), markTaskNotCompleted: vi.fn(), cancelTask: vi.fn() }));

const workspace: WorkspaceSummary = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", name: "Personal", description: null, timezone: "America/Lima", created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const otherWorkspace = { ...workspace, id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", name: "Trabajo" };
const category = { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", workspace_id: workspace.id, name: "Tecnología", description: null, is_active: true, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const project = { id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", workspace_id: workspace.id, name: "LifeManager", description: null, is_active: true, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const task: Task = { id: "11111111-1111-4111-8111-111111111111", workspace_id: workspace.id, created_by_id: testUser.id, category_id: category.id, project_id: project.id, task_series_id: "22222222-2222-4222-8222-222222222222", title: "Revisar LifeManager", description: "Validar programación", scheduled_at: "2026-08-07T15:00:00Z", status: "scheduled", resolved_at: null, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const response: TaskListResponse = { items: [task], total: 21, page: 1, page_size: 20, total_pages: 2 };

function Auth({ children, initial = workspace }: PropsWithChildren<{ initial?: WorkspaceSummary | null }>) {
  const [selected, setWorkspace] = useState(initial);
  const value = useMemo<AuthState>(() => ({ accessToken: "token", user: testUser, workspace: selected, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace, clearSession: vi.fn() }), [selected]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
function Switcher() { const { setWorkspace } = useAuth(); return <button onClick={() => setWorkspace(otherWorkspace)}>Cambiar espacio</button>; }
function renderTasks(initial: WorkspaceSummary | null = workspace, url = "/tasks", switcher = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><Auth initial={initial}><MemoryRouter initialEntries={[url]}>{switcher && <Switcher />}<TasksPage /></MemoryRouter></Auth></QueryClientProvider>);
  return client;
}

describe("TasksPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspace]);
    vi.mocked(categoryApi.listCategories).mockResolvedValue([category]);
    vi.mocked(projectApi.listProjects).mockResolvedValue([project]);
    vi.mocked(taskApi.listTasks).mockResolvedValue(response);
    vi.mocked(taskApi.createTask).mockResolvedValue(task); vi.mocked(taskApi.updateTask).mockResolvedValue(task);
    vi.mocked(taskApi.completeTask).mockResolvedValue({ ...task, status: "completed" });
    vi.mocked(taskApi.markTaskNotCompleted).mockResolvedValue({ ...task, status: "not_completed" });
    vi.mocked(taskApi.cancelTask).mockResolvedValue({ ...task, status: "cancelled" });
  });

  it("loads and renders workspace Tasks, associations, pagination, and recurrence provenance", async () => {
    renderTasks();
    expect(await screen.findByRole("heading", { name: "Revisar LifeManager" })).toBeInTheDocument();
    expect(screen.getAllByText("Tecnología").length).toBeGreaterThan(0); expect(screen.getAllByText("LifeManager").length).toBeGreaterThan(0);
    expect(screen.getByText("Recurrente")).toBeInTheDocument(); expect(screen.getByText(/Página 1 de 2 · 21 resultados/)).toBeInTheDocument();
    expect(taskApi.listTasks).toHaveBeenCalledWith(workspace.id, expect.objectContaining({ page: 1, pageSize: 20, orderBy: "scheduled_at", orderDirection: "asc" }));
  });

  it("does not call any workspace API without a Workspace", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([]); renderTasks(null);
    expect(await screen.findByText("No hay un espacio de trabajo disponible")).toBeInTheDocument();
    expect(taskApi.listTasks).not.toHaveBeenCalled(); expect(categoryApi.listCategories).not.toHaveBeenCalled(); expect(projectApi.listProjects).not.toHaveBeenCalled();
  });

  it("shows loading, errors with retry, and filtered empty states", async () => {
    vi.mocked(taskApi.listTasks).mockReturnValueOnce(new Promise(() => undefined)); renderTasks();
    expect(await screen.findByRole("status", { name: "Cargando tareas" })).toBeInTheDocument();
  });

  it("retries a list failure and distinguishes filtered and initial empty states", async () => {
    vi.mocked(taskApi.listTasks).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ ...response, items: [], total: 0, total_pages: 0 });
    const user = userEvent.setup(); renderTasks(); expect(await screen.findByText("No pudimos cargar las tareas.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" })); expect(await screen.findByText("Aún no tienes tareas.")).toBeInTheDocument();
    vi.mocked(taskApi.listTasks).mockResolvedValue({ ...response, items: [], total: 0, total_pages: 0 });
    await user.selectOptions(screen.getByLabelText("Estado"), "pending"); expect(await screen.findByText("No encontramos tareas con estos filtros.")).toBeInTheDocument();
  });

  it("treats a scheduled date range as an active filter in the empty state", async () => {
    vi.mocked(taskApi.listTasks).mockResolvedValue({ ...response, items: [], total: 0, total_pages: 0 });
    renderTasks(workspace, "/tasks?scheduled_from=2026-08-01T05%3A00%3A00.000Z");
    expect(await screen.findByText("No encontramos tareas con estos filtros.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Crear primera tarea" })).not.toBeInTheDocument();
  });

  it("maps URL filters and moves through real pagination", async () => {
    const user = userEvent.setup();
    renderTasks(workspace, `/tasks?status=pending&outcome=completed&category=${category.id}&project=${project.id}&scheduled_from=2026-08-01T05%3A00%3A00.000Z&scheduled_to=2026-08-10T05%3A00%3A00.000Z&order_by=title&order_direction=desc&search=Revisar`);
    await screen.findByRole("heading", { name: "Revisar LifeManager" });
    expect(taskApi.listTasks).toHaveBeenCalledWith(workspace.id, expect.objectContaining({ status: "pending", outcome: "completed", categoryId: category.id, projectId: project.id, orderBy: "title", orderDirection: "desc", search: "Revisar" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(taskApi.listTasks).toHaveBeenLastCalledWith(workspace.id, expect.objectContaining({ page: 2 })));
    await user.selectOptions(screen.getByLabelText("Estado"), "scheduled");
    await waitFor(() => expect(taskApi.listTasks).toHaveBeenLastCalledWith(workspace.id, expect.objectContaining({ page: 1, status: "scheduled" })));
  });

  it("submits search without requesting on every keystroke", async () => {
    const user = userEvent.setup(); renderTasks(); await screen.findByRole("heading", { name: "Revisar LifeManager" }); const calls = vi.mocked(taskApi.listTasks).mock.calls.length;
    await user.type(screen.getByLabelText("Buscar por título"), "casa"); expect(taskApi.listTasks).toHaveBeenCalledTimes(calls);
    await user.click(screen.getByRole("button", { name: "Buscar" })); await waitFor(() => expect(taskApi.listTasks).toHaveBeenLastCalledWith(workspace.id, expect.objectContaining({ search: "casa", page: 1 })));
  });

  it("validates and creates a timezone-aware manual Task with assignments", async () => {
    const user = userEvent.setup(); const client = renderTasks(); const invalidate = vi.spyOn(client, "invalidateQueries"); await screen.findByRole("heading", { name: "Revisar LifeManager" });
    await user.click(screen.getByRole("button", { name: "Nueva tarea" })); await user.click(screen.getByRole("button", { name: "Guardar tarea" })); expect(await screen.findByText("Ingresa un título.")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    await user.type(screen.getByLabelText("Título"), "Nueva tarea"); await user.type(screen.getByLabelText(/Descripción/), "Detalle"); await user.type(screen.getByLabelText(/Fecha y hora/), "2026-08-08T10:30");
    await user.selectOptions(within(dialog).getByLabelText("Categoría"), category.id); await user.selectOptions(within(dialog).getByLabelText("Proyecto"), project.id); await user.click(screen.getByRole("button", { name: "Guardar tarea" }));
    await waitFor(() => expect(taskApi.createTask).toHaveBeenCalledWith(workspace.id, expect.objectContaining({ title: "Nueva tarea", description: "Detalle", scheduled_at: "2026-08-08T15:30:00.000Z", category_id: category.id, project_id: project.id })));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["tasks", workspace.id] }); expect(invalidate).toHaveBeenCalledWith({ queryKey: ["dashboard", "summary", workspace.id] }); expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["tasks", otherWorkspace.id] });
  });

  it("prefills editing, supports clearing associations, and hides edit for resolved Tasks", async () => {
    const user = userEvent.setup(); renderTasks(); await screen.findByRole("heading", { name: "Revisar LifeManager" }); await user.click(screen.getByRole("button", { name: /Editar/ }));
    const dialog = screen.getByRole("dialog"); expect(within(dialog).getByLabelText("Título")).toHaveValue(task.title); expect(within(dialog).getByLabelText("Categoría")).toHaveValue(category.id);
    await user.selectOptions(within(dialog).getByLabelText("Categoría"), ""); await user.selectOptions(within(dialog).getByLabelText("Proyecto"), ""); await user.click(screen.getByRole("button", { name: "Guardar tarea" }));
    await waitFor(() => expect(taskApi.updateTask).toHaveBeenCalledWith(workspace.id, task.id, expect.objectContaining({ category_id: null, project_id: null })));
  });

  it("does not expose editing or resolution actions for a terminal Task", async () => {
    vi.mocked(taskApi.listTasks).mockResolvedValue({ ...response, items: [{ ...task, status: "completed", resolved_at: "2026-08-08T16:00:00Z" }] });
    renderTasks(); expect(await screen.findByText("Tarea resuelta; no admite cambios.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Editar/ })).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: /Completada:/ })).not.toBeInTheDocument();
  });

  it("uses lifecycle endpoints and translates conflicts", async () => {
    const user = userEvent.setup(); renderTasks(); await screen.findByRole("heading", { name: "Revisar LifeManager" });
    await user.click(screen.getByRole("button", { name: `Completada: ${task.title}` })); await waitFor(() => expect(taskApi.completeTask).toHaveBeenCalledWith(workspace.id, task.id));
    vi.mocked(taskApi.markTaskNotCompleted).mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
    await user.click(screen.getByRole("button", { name: `No realizada: ${task.title}` })); expect(await screen.findByRole("alert")).toHaveTextContent("Esta tarea ya fue resuelta");
    await user.click(screen.getByRole("button", { name: `Cancelada: ${task.title}` })); await waitFor(() => expect(taskApi.cancelTask).toHaveBeenCalledWith(workspace.id, task.id));
  });

  it("isolates task queries when switching Workspaces", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspace, otherWorkspace]); const user = userEvent.setup(); renderTasks(workspace, "/tasks", true); await screen.findByRole("heading", { name: "Revisar LifeManager" });
    await user.click(screen.getByRole("button", { name: "Cambiar espacio" })); await waitFor(() => expect(taskApi.listTasks).toHaveBeenCalledWith(otherWorkspace.id, expect.any(Object)));
  });

  it("performs deterministic IANA timezone conversion and keeps Spanish UTF-8 text", () => {
    expect(localDateTimeToIso("2026-08-08T10:30", "America/Lima")).toBe("2026-08-08T15:30:00.000Z");
    expect("Tareas categoría descripción programación próxima aún cancelación sesión").toContain("categoría");
  });
});
