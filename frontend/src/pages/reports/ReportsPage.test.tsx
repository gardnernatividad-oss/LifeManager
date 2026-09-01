import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useMemo, useState, type PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as catalogApi from "../../api/v2CatalogApi";
import * as reportApi from "../../api/v2ReportApi";
import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { WorkspaceSummary } from "../../types/auth";
import type { V2Category } from "../../types/v2Catalog";
import type { V2ActivityReport, V2PendingReport, V2ProjectReport, V2ReportSummary, V2TaskReport } from "../../types/v2Report";
import { ReportsPage } from "./ReportsPage";

vi.mock("../../api/v2CatalogApi", () => ({ listV2Catalog: vi.fn() }));
vi.mock("../../api/v2ReportApi", () => ({ getV2ReportSummary: vi.fn(), getV2TaskReport: vi.fn(), getV2PendingReport: vi.fn(), getV2ProjectReport: vi.fn(), getV2ActivityReport: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({ listWorkspaceMembers: vi.fn() }));

const personal: WorkspaceSummary = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", name: "Personal", kind: "PERSONAL", timezone: "America/Lima" };
const shared: WorkspaceSummary = { ...personal, id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", name: "Familia", kind: "SHARED" };
const category: V2Category = { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", workspace_id: personal.id, name: "Hogar", is_active: true, lock_version: 1, can_delete: false, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const summary: V2ReportSummary = { local_date: "2026-08-31", date_from: "2026-08-02", date_until: "2026-08-31", category_id: null, responsible_user_id: null, counts: { tasks: 4, pending_items: 3, projects: 2, activities: 1, total: 10 } };
const progress = { total_count: 2, no_iniciado_count: 0, en_proceso_count: 1, finalizado_count: 1, average_progress: "60.00" };
const compliance = { en_plazo_count: 0, atrasado_count: 1, con_adelanto_count: 0, a_tiempo_count: 1, con_retraso_count: 0 };
const taskReport: V2TaskReport = { period: { date_from: null, date_until: null }, filters: {}, master_task_id: null, custom_tasks: null, summary: { total_count: 2, pending_count: 0, completed_count: 1, not_completed_count: 1, resolved_count: 2, completion_rate: "50.00" }, by_task: [{ key: "CUSTOM", label: "Otras tareas", total_count: 1, pending_count: 0, completed_count: 1, not_completed_count: 0, resolved_count: 1, completion_rate: "100.00" }], by_category: [], evolution: [] };
const pendingReport: V2PendingReport = { period: { date_from: null, date_until: null }, filters: {}, summary: progress, compliance, by_category: [], evolution: [] };
const projectReport: V2ProjectReport = { period: { date_from: null, date_until: null }, filters: {}, summary: progress, stage_compliance: compliance, by_category: [], by_project: [{ project_id: "project-1", project_name: "Mudanza", category_id: category.id, category_name: "Hogar", planned_date: "2026-08-31", progress: "60.00", state: "EN_PROCESO", stage_count: 2 }], evolution: [] };
const activityReport: V2ActivityReport = { period: { date_from: null, date_until: null }, filters: {}, activity_master_id: null, custom_activities: null, summary: { total_count: 2, scheduled_count: 1, cancelled_count: 1, total_duration_minutes: "150.00", average_duration_minutes: "75.00" }, by_activity: [{ key: "CUSTOM", label: "Otras actividades", total_count: 1, scheduled_count: 1, cancelled_count: 0, total_duration_minutes: "90.00", average_duration_minutes: "90.00" }], by_category: [], by_organizer: [], evolution: [{ local_date: "2026-08-31", total_count: 2, scheduled_count: 1, cancelled_count: 1, total_duration_minutes: "150.00", average_duration_minutes: "75.00" }] };

function Auth({ children, initial = personal }: PropsWithChildren<{ initial?: WorkspaceSummary | null }>) {
  const [workspace, setWorkspace] = useState(initial);
  const value = useMemo<AuthState>(() => ({ user: testUser, workspace, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace, clearSession: vi.fn(), setAuthenticatedUser: vi.fn() }), [workspace]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
function Switcher() { const { setWorkspace } = useAuth(); return <button onClick={() => setWorkspace(shared)}>Cambiar espacio</button>; }
function renderPage(initial: WorkspaceSummary | null = personal, switcher = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  render(<QueryClientProvider client={client}><Auth initial={initial}><MemoryRouter>{switcher ? <Switcher /> : null}<ReportsPage /></MemoryRouter></Auth></QueryClientProvider>);
}

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-31T12:00:00Z"));
    vi.mocked(catalogApi.listV2Catalog).mockResolvedValue({ items: [category], total: 1 });
    vi.mocked(workspaceApi.listWorkspaceMembers).mockResolvedValue([{ user_id: testUser.id, display_name: "Ada Lovelace", email: testUser.email, role: "Miembro", status: "ACTIVE", joined_at: "2026-01-01T00:00:00Z", ended_at: null }]);
    vi.mocked(reportApi.getV2ReportSummary).mockResolvedValue(summary);
    vi.mocked(reportApi.getV2TaskReport).mockResolvedValue(taskReport);
    vi.mocked(reportApi.getV2PendingReport).mockResolvedValue(pendingReport);
    vi.mocked(reportApi.getV2ProjectReport).mockResolvedValue(projectReport);
    vi.mocked(reportApi.getV2ActivityReport).mockResolvedValue(activityReport);
  });

  it("loads a Personal Workspace summary with the default local period", async () => {
    renderPage();
    expect(await screen.findByText("Total de registros:")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByLabelText("Responsable")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(reportApi.getV2ReportSummary).toHaveBeenCalledWith(personal.id, { date_from: "2026-08-02", date_until: "2026-08-31" });
  });

  it("applies Category and responsible filters in a Shared Workspace", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage(shared);
    await screen.findByText("Total de registros:");
    await user.selectOptions(screen.getByLabelText("Categoría"), category.id);
    await user.selectOptions(screen.getByLabelText("Responsable"), testUser.id);
    await waitFor(() => expect(reportApi.getV2ReportSummary).toHaveBeenLastCalledWith(shared.id, expect.objectContaining({ category_id: category.id, responsible_user_id: testUser.id })));
  });

  it("supports an open custom period and rejects a reversed range", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await screen.findByText("Total de registros:");
    await user.selectOptions(screen.getByLabelText("Periodo"), "CUSTOM");
    await user.type(screen.getByLabelText("Desde"), "2026-08-10");
    await waitFor(() => expect(reportApi.getV2ReportSummary).toHaveBeenLastCalledWith(personal.id, { date_from: "2026-08-10" }));
    await user.type(screen.getByLabelText("Hasta"), "2026-08-01");
    expect(await screen.findByText("La fecha Desde no puede ser posterior a Hasta.")).toBeInTheDocument();
  });

  it("waits for filter options and retries them safely", async () => {
    vi.mocked(catalogApi.listV2Catalog).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ items: [category], total: 1 });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    expect(await screen.findByText("No pudimos cargar las opciones de filtros.")).toBeInTheDocument();
    expect(reportApi.getV2ReportSummary).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Total de registros:")).toBeInTheDocument();
  });

  it("renders recoverable error and empty states", async () => {
    vi.mocked(reportApi.getV2ReportSummary).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ ...summary, counts: { tasks: 0, pending_items: 0, projects: 0, activities: 0, total: 0 } });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    expect(await screen.findByText("No pudimos cargar el resumen de Reportes.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No hay datos para estos filtros")).toBeInTheDocument();
  });

  it("isolates queries when the selected Workspace changes", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage(personal, true);
    await waitFor(() => expect(reportApi.getV2ReportSummary).toHaveBeenCalledWith(personal.id, expect.any(Object)));
    await user.click(screen.getByRole("button", { name: "Cambiar espacio" }));
    await waitFor(() => expect(reportApi.getV2ReportSummary).toHaveBeenCalledWith(shared.id, expect.any(Object)));
  });

  it("does not query without a selected Workspace", () => {
    renderPage(null);
    expect(screen.getByText("Selecciona un espacio de trabajo")).toBeInTheDocument();
    expect(catalogApi.listV2Catalog).not.toHaveBeenCalled();
    expect(reportApi.getV2ReportSummary).not.toHaveBeenCalled();
  });

  it("renders detailed Task results and the Otras tareas grouping", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await user.click(screen.getByRole("button", { name: "Tareas" }));
    expect(await screen.findByText("Resultados de Tareas")).toBeInTheDocument();
    expect(screen.getAllByText("Otras tareas").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Tarea"), "CUSTOM");
    await waitFor(() => expect(reportApi.getV2TaskReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ custom_tasks: true })));
  });

  it("renders Pending and Project progress and compliance", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await user.click(screen.getByRole("button", { name: "Pendientes" }));
    expect(await screen.findByText("Avance de Pendientes")).toBeInTheDocument();
    expect(screen.getByText("60.00%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Proyectos" }));
    expect(await screen.findByText("Cumplimiento de Etapas")).toBeInTheDocument();
    expect(screen.getByText("Mudanza")).toBeInTheDocument();
    expect(screen.getByText("31/08/2026")).toBeInTheDocument();
  });

  it("loads Activity filters and renders duration without compliance", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await user.click(screen.getByRole("button", { name: "Actividades" }));
    expect(await screen.findByText("Cantidad y duración de ocurrencias persistidas.")).toBeInTheDocument();
    expect(screen.getAllByText("Otras actividades").length).toBeGreaterThan(0);
    expect(screen.getAllByText("150.00 min").length).toBeGreaterThan(0);
    expect(screen.queryByText("Cumplimiento")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Actividad"), "CUSTOM");
    await waitFor(() => expect(reportApi.getV2ActivityReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ custom_activities: true })));
  });

  it("retries Activity filter and report failures and renders the empty state", async () => {
    vi.mocked(catalogApi.listV2Catalog)
      .mockResolvedValueOnce({ items: [category], total: 1 })
      .mockRejectedValueOnce(new Error("masters offline"))
      .mockResolvedValueOnce({ items: [], total: 0 });
    vi.mocked(reportApi.getV2ActivityReport)
      .mockRejectedValueOnce(new Error("report offline"))
      .mockResolvedValueOnce({ ...activityReport, summary: { ...activityReport.summary, total_count: 0 } });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await user.click(screen.getByRole("button", { name: "Actividades" }));
    expect(await screen.findByText("No pudimos cargar las opciones de filtros.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No pudimos cargar el reporte de Actividades.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No hay Actividades para estos filtros")).toBeInTheDocument();
  });

  it("uses the responsible contract as Organizer for Shared Activity reports", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage(shared);
    await user.click(screen.getByRole("button", { name: "Actividades" }));
    await screen.findByText("Cantidad y duración de ocurrencias persistidas.");
    await user.selectOptions(screen.getByLabelText("Organizador"), testUser.id);
    await waitFor(() => expect(reportApi.getV2ActivityReport).toHaveBeenLastCalledWith(shared.id, expect.objectContaining({ responsible_user_id: testUser.id })));
  });

  it("shows the documented person filter with domain-specific labels", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    expect(await screen.findByLabelText("Responsable")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Tareas" }));
    expect(await screen.findByLabelText("Responsable")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Responsable"), testUser.id);
    await waitFor(() => expect(reportApi.getV2TaskReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ responsible_user_id: testUser.id })));

    await user.click(screen.getByRole("button", { name: "Pendientes" }));
    expect(screen.getByLabelText("Responsable")).toBeInTheDocument();
    await waitFor(() => expect(reportApi.getV2PendingReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ responsible_user_id: testUser.id })));

    await user.click(screen.getByRole("button", { name: "Proyectos" }));
    expect(screen.getByLabelText("Líder")).toBeInTheDocument();
    await waitFor(() => expect(reportApi.getV2ProjectReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ responsible_user_id: testUser.id })));

    await user.click(screen.getByRole("button", { name: "Actividades" }));
    expect(screen.getByLabelText("Organizador")).toBeInTheDocument();
    await waitFor(() => expect(reportApi.getV2ActivityReport).toHaveBeenLastCalledWith(personal.id, expect.objectContaining({ responsible_user_id: testUser.id })));
  });
});
