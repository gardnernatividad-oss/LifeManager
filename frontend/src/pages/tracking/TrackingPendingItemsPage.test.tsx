import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as categoryApi from "../../api/planningPendingItemApi";
import * as homeApi from "../../api/homeApi";
import { queryKeys } from "../../api/queryKeys";
import * as api from "../../api/trackingPendingItemApi";
import { useAuth } from "../../hooks/useAuth";
import type { PlanningPendingItem } from "../../types/planningPendingItem";
import { formatLocalTimestamp } from "../../utils/localizedDate";
import { TrackingPendingItemsPage } from "./TrackingPendingItemsPage";

vi.mock("../../api/trackingPendingItemApi", () => ({ listTrackingPendingItems: vi.fn(), saveTrackingPendingItems: vi.fn() }));
vi.mock("../../api/planningPendingItemApi", () => ({ listAllCategoryOptions: vi.fn() }));
vi.mock("../../api/homeApi", () => ({ getHomeSummary: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const category = { id: "category", name: "Personal", created_at: "", updated_at: "" };
function item(id: string, state: PlanningPendingItem["state"], compliance: string | null, detailDays: number | null, active = true): PlanningPendingItem {
  const progress = state === "NO_INICIADO" ? 0 : state === "FINALIZADO" ? 100 : 45;
  return { id, category_id: category.id, category, name: `Pendiente ${id}`, is_active: active, planned_date: active ? "2026-08-13" : null, progress, state, completion_date: progress === 100 ? "2026-08-12" : null, compliance, detail_days: detailDays, comment: id === "one" ? "Comentario actual" : null, lock_version: id === "one" ? 3 : 7, created_at: "", updated_at: "" };
}
const rows = [
  item("one", "NO_INICIADO", "EN_PLAZO", 1), item("two", "EN_PROCESO", "ATRASADO", 3), item("three", "FINALIZADO", "CON_ADELANTO", 2),
  item("four", "FINALIZADO", "A_TIEMPO", 0), item("five", "FINALIZADO", "CON_RETRASO", 4), item("six", "NO_INICIADO", null, null, false)
];
const response = { items: rows, total: 30, page: 1, page_size: 25, total_pages: 2 };
const home = { user_first_name: "Ana", local_date: "2026-08-13", tasks: { due_today: 0, overdue: 0 }, pending_items: { overdue: 0 }, project_steps: { overdue: 0 }, last_review_saved_at: null, pending_items_last_tracking_saved_at: "2026-08-12T18:00:00Z" };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><TrackingPendingItemsPage /></QueryClientProvider>);
  return invalidate;
}

describe("TrackingPendingItemsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ user: { timezone: "America/Lima" } } as ReturnType<typeof useAuth>);
    vi.mocked(categoryApi.listAllCategoryOptions).mockResolvedValue([category]);
    vi.mocked(homeApi.getHomeSummary).mockResolvedValue(home);
    vi.mocked(api.listTrackingPendingItems).mockResolvedValue(response);
    vi.mocked(api.saveTrackingPendingItems).mockResolvedValue({ items: rows, saved_at: "2026-08-13T18:30:00Z" });
  });

  it("shows the persisted Home timestamp on initial load", async () => {
    renderPage(); expect(await screen.findByText(`Última actualización: ${formatLocalTimestamp(home.pending_items_last_tracking_saved_at, "America/Lima")}`)).toBeInTheDocument(); expect(homeApi.getHomeSummary).toHaveBeenCalledTimes(1);
  });

  it("handles null persisted history with the shared timestamp convention", async () => {
    vi.mocked(homeApi.getHomeSummary).mockResolvedValue({ ...home, pending_items_last_tracking_saved_at: null }); renderPage(); expect(await screen.findByText("Última actualización: Sin registro")).toBeInTheDocument();
  });

  it("renders the complete compact register and every derived label", async () => {
    renderPage(); const register = await screen.findByRole("table", { name: "Registro de Pendientes de Seguimiento" });
    for (const header of ["Vigencia", "Fecha planificada", "Fecha de cumplimiento", "Pendiente", "Categoría", "Avance", "Estado", "Cumplimiento", "Detalle", "Comentario"]) expect(within(register).getByRole("columnheader", { name: header })).toBeInTheDocument();
    expect(within(register).getAllByText("12/08/2026").length).toBeGreaterThan(0);
    for (const label of ["No iniciado", "En proceso", "Finalizado", "En plazo", "Atrasado", "Con adelanto", "A tiempo", "Con retraso", "1 día", "3 días", "—"]) expect(within(register).getAllByText(label).length).toBeGreaterThan(0);
    expect(within(register).getByDisplayValue("Comentario actual")).toBeInTheDocument();
  });

  it("keeps Planning fields read-only and offers only valid Vigencia transitions", async () => {
    renderPage(); await screen.findByRole("table");
    expect(screen.queryByLabelText(/Nombre de|Categoría de|Fecha planificada de/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Vigencia de Pendiente one")).toHaveValue("true");
    expect(screen.queryByLabelText("Vigencia de Pendiente six")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /eliminar/i })).not.toBeInTheDocument();
  });

  it("keeps multiple rows dirty, omits unchanged rows and submits one exact batch", async () => {
    const user = userEvent.setup(); renderPage();
    await user.selectOptions(await screen.findByLabelText("Vigencia de Pendiente one"), "false"); await user.clear(screen.getByLabelText("Avance de Pendiente one")); await user.type(screen.getByLabelText("Avance de Pendiente one"), "25");
    await user.type(screen.getByLabelText("Comentario de Pendiente two"), "Nuevo");
    expect(api.saveTrackingPendingItems).not.toHaveBeenCalled(); expect(screen.getByText("2 con cambios")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.saveTrackingPendingItems).toHaveBeenCalledTimes(1));
    expect(api.saveTrackingPendingItems).toHaveBeenCalledWith([{ id: "one", lock_version: 3, is_active: false, progress: 25 }, { id: "two", lock_version: 7, comment: "Nuevo" }]);
  });

  it("validates progress locally and does not autosave", async () => {
    const user = userEvent.setup(); renderPage(); const input = await screen.findByLabelText("Avance de Pendiente one");
    await user.clear(input); await user.type(input, "101");
    expect(screen.getByRole("alert")).toHaveTextContent("entre 0 y 100"); expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled(); expect(api.saveTrackingPendingItems).not.toHaveBeenCalled();
  });

  it("uses all server filters and approved pagination", async () => {
    const user = userEvent.setup(); renderPage(); await screen.findByRole("table");
    expect(screen.getByLabelText("Estado")).toHaveValue("unfinished"); expect(api.listTrackingPendingItems).toHaveBeenCalledWith(expect.objectContaining({ is_active: true, unfinished: true }));
    await user.selectOptions(screen.getByLabelText("Vigencia"), "false"); await user.selectOptions(screen.getByLabelText("Categoría"), category.id); await user.selectOptions(screen.getByLabelText("Estado"), "FINALIZADO"); await user.selectOptions(screen.getByLabelText("Cumplimiento"), "CON_RETRASO"); await user.type(screen.getByLabelText("Desde"), "2026-08-01"); await user.type(screen.getByLabelText("Hasta"), "2026-08-31");
    await waitFor(() => expect(api.listTrackingPendingItems).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 25, is_active: false, category_id: category.id, state: "FINALIZADO", compliance: "CON_RETRASO", planned_from: "2026-08-01", planned_to: "2026-08-31", unfinished: undefined })));
    expect(within(screen.getByLabelText("Por página")).getAllByRole("option").map((option) => option.textContent)).toEqual(["25", "50", "100"]); await user.click(screen.getByRole("button", { name: "Siguiente" })); await waitFor(() => expect(api.listTrackingPendingItems).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("clears stale edits on 409 but preserves them on a retryable generic error", async () => {
    const user = userEvent.setup(); vi.mocked(api.saveTrackingPendingItems).mockRejectedValueOnce({ isAxiosError: true, response: { status: 409 } }).mockRejectedValueOnce(new Error("network")); const invalidate = renderPage();
    await user.type(await screen.findByLabelText("Comentario de Pendiente two"), "stale"); await user.click(screen.getByRole("button", { name: "Guardar" })); expect(await screen.findByRole("alert")).toHaveTextContent("cambiaron desde la última carga"); expect(screen.getByText("0 con cambios")).toBeInTheDocument(); expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.trackingPendingItemsRoot });
    await user.type(screen.getByLabelText("Comentario de Pendiente two"), "retry"); await user.click(screen.getByRole("button", { name: "Guardar" })); expect(await screen.findByRole("alert")).toHaveTextContent("siguen pendientes"); expect(screen.getByText("1 con cambios")).toBeInTheDocument();
  });

  it("clears dirty state, shows saved timestamp and invalidates only related roots after success", async () => {
    const user = userEvent.setup(); const invalidate = renderPage(); await user.type(await screen.findByLabelText("Comentario de Pendiente two"), "Guardado"); await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText(/Última actualización:/)).toBeInTheDocument(); expect(screen.getByText("0 con cambios")).toBeInTheDocument();
    await waitFor(() => { for (const key of [queryKeys.trackingPendingItemsRoot, queryKeys.planningPendingItemsRoot, queryKeys.review, queryKeys.home, queryKeys.pendingItemReportsRoot]) expect(invalidate).toHaveBeenCalledWith({ queryKey: key }); });
  });

  it("obtains the saved timestamp from Home after a remount", async () => {
    const saved = "2026-08-13T18:30:00Z"; const expected = `Última actualización: ${formatLocalTimestamp(saved, "America/Lima")}`;
    const user = userEvent.setup(); renderPage(); await user.type(await screen.findByLabelText("Comentario de Pendiente two"), "Guardado"); await user.click(screen.getByRole("button", { name: "Guardar" })); await screen.findByText(expected);
    cleanup(); vi.mocked(homeApi.getHomeSummary).mockResolvedValue({ ...home, pending_items_last_tracking_saved_at: saved }); renderPage(); expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it("shows loading, GET retry and the approved empty state", async () => {
    let resolve!: (value: typeof response) => void; vi.mocked(api.listTrackingPendingItems).mockReturnValueOnce(new Promise((done) => { resolve = done; })); renderPage(); expect(screen.getByText("Cargando Pendientes…")).toBeInTheDocument(); resolve(response); await screen.findByRole("table");
    vi.mocked(api.listTrackingPendingItems).mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce({ ...response, items: [], total: 0, total_pages: 0 }); const user = userEvent.setup(); await user.selectOptions(screen.getByLabelText("Vigencia"), ""); expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar los Pendientes"); await user.click(screen.getByRole("button", { name: "Reintentar" })); expect(await screen.findByText("No hay Pendientes para los filtros seleccionados.")).toHaveClass("review-empty");
  });
});
