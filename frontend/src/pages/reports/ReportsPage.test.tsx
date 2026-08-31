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
import type { V2ReportSummary } from "../../types/v2Report";
import { ReportsPage } from "./ReportsPage";

vi.mock("../../api/v2CatalogApi", () => ({ listV2Catalog: vi.fn() }));
vi.mock("../../api/v2ReportApi", () => ({ getV2ReportSummary: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({ listWorkspaceMembers: vi.fn() }));

const personal: WorkspaceSummary = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", name: "Personal", kind: "PERSONAL", timezone: "America/Lima" };
const shared: WorkspaceSummary = { ...personal, id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", name: "Familia", kind: "SHARED" };
const category: V2Category = { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", workspace_id: personal.id, name: "Hogar", is_active: true, lock_version: 1, can_delete: false, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" };
const summary: V2ReportSummary = { local_date: "2026-08-31", date_from: "2026-08-02", date_until: "2026-08-31", category_id: null, responsible_user_id: null, counts: { tasks: 4, pending_items: 3, projects: 2, activities: 1, total: 10 } };

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
  });

  it("loads a Personal Workspace summary with the default local period", async () => {
    renderPage();
    expect(await screen.findByText("Total de registros:")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.queryByLabelText("Responsable")).not.toBeInTheDocument();
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
});
