import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRef, useMemo, useState, type PropsWithChildren } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as dashboardApi from "../../api/dashboardApi";
import * as workspaceApi from "../../api/workspaceApi";
import { Topbar } from "../../components/layout/Topbar";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { WorkspaceSummary } from "../../types/auth";
import type { DashboardStatistics, DashboardSummary } from "../../types/dashboard";
import { DashboardPage } from "./DashboardPage";

vi.mock("../../api/workspaceApi", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../api/dashboardApi", () => ({
  getDashboardSummary: vi.fn(),
  getDashboardStatistics: vi.fn()
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

const summary: DashboardSummary = {
  pending_tasks: 4,
  scheduled_tasks: 6,
  completed_tasks: 8,
  not_completed_tasks: 2,
  cancelled_tasks: 1,
  total_tasks: 21,
  tasks_due_today: 3,
  tasks_due_next_7_days: 5,
  overdue_tasks: 2
};

const statistics: DashboardStatistics = {
  completion_rate: 72.73,
  completed_tasks: 8,
  not_completed_tasks: 2,
  cancelled_tasks: 1,
  resolved_tasks: 11,
  pending_tasks: 4,
  scheduled_tasks: 6
};

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

function renderDashboard(initialWorkspace: WorkspaceSummary | null = null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <StatefulAuth initialWorkspace={initialWorkspace}>
        <MemoryRouter>
          <Topbar
            isMenuOpen={false}
            menuButtonRef={createRef<HTMLButtonElement>()}
            onMenuToggle={vi.fn()}
          />
          <DashboardPage />
        </MemoryRouter>
      </StatefulAuth>
    </QueryClientProvider>
  );
  return queryClient;
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(workspaceApi.listWorkspaces).mockReset();
    vi.mocked(dashboardApi.getDashboardSummary).mockReset();
    vi.mocked(dashboardApi.getDashboardStatistics).mockReset();
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne]);
    vi.mocked(dashboardApi.getDashboardSummary).mockResolvedValue(summary);
    vi.mocked(dashboardApi.getDashboardStatistics).mockResolvedValue(statistics);
  });

  it("loads Workspaces and selects the first available Workspace", async () => {
    renderDashboard();

    expect((await screen.findAllByText("Hogar")).length).toBeGreaterThanOrEqual(1);
    await waitFor(() => expect(dashboardApi.getDashboardSummary).toHaveBeenCalledWith(workspaceOne.id));
    expect(workspaceApi.listWorkspaces).toHaveBeenCalledOnce();
  });

  it("preserves an existing selected Workspace that remains available", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne, workspaceTwo]);
    renderDashboard(workspaceTwo);

    expect(await screen.findByLabelText("Espacio de trabajo")).toHaveValue(workspaceTwo.id);
    await waitFor(() => expect(dashboardApi.getDashboardSummary).toHaveBeenCalledWith(workspaceTwo.id));
    expect(dashboardApi.getDashboardSummary).not.toHaveBeenCalledWith(workspaceOne.id);
  });

  it("renders a selector and reloads isolated Dashboard queries when Workspace changes", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([workspaceOne, workspaceTwo]);
    const user = userEvent.setup();
    const queryClient = renderDashboard(workspaceOne);
    const selector = await screen.findByLabelText("Espacio de trabajo");
    await waitFor(() => expect(dashboardApi.getDashboardSummary).toHaveBeenCalledWith(workspaceOne.id));

    await user.selectOptions(selector, workspaceTwo.id);

    await waitFor(() => expect(dashboardApi.getDashboardSummary).toHaveBeenCalledWith(workspaceTwo.id));
    expect(dashboardApi.getDashboardStatistics).toHaveBeenCalledWith(workspaceTwo.id);
    expect(queryClient.getQueryData(["dashboard", "summary", workspaceOne.id])).toEqual(summary);
    expect(queryClient.getQueryData(["dashboard", "summary", workspaceTwo.id])).toEqual(summary);
  });

  it("shows a stable loading state while Workspaces load", () => {
    vi.mocked(workspaceApi.listWorkspaces).mockReturnValue(new Promise(() => undefined));
    renderDashboard();

    expect(screen.getByRole("status", { name: "Cargando Dashboard" })).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows a useful empty state when no Workspaces are available", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValue([]);
    renderDashboard();

    expect(await screen.findByText("No tienes un espacio de trabajo disponible")).toBeInTheDocument();
    expect(dashboardApi.getDashboardSummary).not.toHaveBeenCalled();
  });

  it("shows a Workspace loading failure with a retry action", async () => {
    vi.mocked(workspaceApi.listWorkspaces)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([workspaceOne]);
    const user = userEvent.setup();
    renderDashboard();

    expect(await screen.findByText(/No pudimos cargar tus espacios de trabajo/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect((await screen.findAllByText("Hogar")).length).toBeGreaterThanOrEqual(1);
    expect(workspaceApi.listWorkspaces).toHaveBeenCalledTimes(2);
  });

  it("renders every Summary metric with actual API values and emphasizes attention", async () => {
    renderDashboard(workspaceOne);

    const metrics = await screen.findByRole("heading", { name: "Resumen de tareas" });
    const section = metrics.closest("section");
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText("Próximos 7 días")).toBeInTheDocument();
    expect(within(section as HTMLElement).getByText("21")).toBeInTheDocument();
    const attentionSection = screen.getByRole("heading", { name: "Requiere atención" }).closest("section");
    expect(within(attentionSection as HTMLElement).getByText("Vencidas").closest("article")).toHaveClass("attention-card--overdue");
    expect(screen.getByText("Tareas previstas para el día de hoy")).toBeInTheDocument();
  });

  it("renders Statistics and accessible completion progress", async () => {
    renderDashboard(workspaceOne);

    expect(await screen.findByText("72.73%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Tasa de finalización" })).toHaveAttribute(
      "aria-valuenow",
      "72.73"
    );
    expect(screen.getByText("Resueltas").nextElementSibling).toHaveTextContent("11");
  });

  it("treats a zero-data Workspace as an empty success and keeps quick actions", async () => {
    vi.mocked(dashboardApi.getDashboardSummary).mockResolvedValue(
      Object.fromEntries(Object.keys(summary).map((field) => [field, 0])) as unknown as DashboardSummary
    );
    vi.mocked(dashboardApi.getDashboardStatistics).mockResolvedValue({
      ...statistics,
      completion_rate: 0,
      completed_tasks: 0,
      not_completed_tasks: 0,
      cancelled_tasks: 0,
      resolved_tasks: 0,
      pending_tasks: 0,
      scheduled_tasks: 0
    });
    renderDashboard(workspaceOne);

    expect(await screen.findByText("Tu espacio todavía no tiene tareas")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tareas" })).toHaveAttribute("href", "/tasks");
    expect(screen.getByRole("link", { name: "Tareas recurrentes" })).toHaveAttribute("href", "/tasks/recurring");
    expect(screen.getByRole("link", { name: "Seguimiento diario" })).toHaveAttribute("href", "/daily-workflow");
    expect(screen.getByRole("link", { name: "Proyectos" })).toHaveAttribute("href", "/projects");
  });

  it("keeps successful Statistics visible when Summary fails and retries Summary", async () => {
    vi.mocked(dashboardApi.getDashboardSummary)
      .mockRejectedValueOnce(new Error("summary unavailable"))
      .mockResolvedValueOnce(summary);
    const user = userEvent.setup();
    renderDashboard(workspaceOne);

    expect(await screen.findByText("No pudimos cargar el resumen de tareas.")).toBeInTheDocument();
    expect(screen.getByText("72.73%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByRole("heading", { name: "Resumen de tareas" })).toBeInTheDocument();
    expect(dashboardApi.getDashboardSummary).toHaveBeenCalledTimes(2);
  });

  it("handles Statistics failure without discarding Summary", async () => {
    vi.mocked(dashboardApi.getDashboardStatistics).mockRejectedValue(new Error("statistics unavailable"));
    renderDashboard(workspaceOne);

    expect(await screen.findByRole("heading", { name: "Resumen de tareas" })).toBeInTheDocument();
    expect(screen.getByText("El resumen está disponible, pero no pudimos cargar las estadísticas.")).toBeInTheDocument();
  });

  it("manually refreshes both Dashboard endpoints", async () => {
    const user = userEvent.setup();
    renderDashboard(workspaceOne);
    const refresh = await screen.findByRole("button", { name: "Actualizar Dashboard" });
    await user.click(refresh);

    await waitFor(() => expect(dashboardApi.getDashboardSummary).toHaveBeenCalledTimes(2));
    expect(dashboardApi.getDashboardStatistics).toHaveBeenCalledTimes(2);
  });
});
