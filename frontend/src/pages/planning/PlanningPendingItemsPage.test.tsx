import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/planningPendingItemApi";
import type { PendingItemListResponse, PlanningPendingItem } from "../../types/planningPendingItem";
import { PlanningPendingItemsPage } from "./PlanningPendingItemsPage";

vi.mock("../../api/planningPendingItemApi", () => ({ listAllCategoryOptions: vi.fn(), listPlanningPendingItems: vi.fn(), createPlanningPendingItem: vi.fn(), updatePlanningPendingItem: vi.fn() }));

const categories = [{ id: "category-1", name: "Personal", created_at: "", updated_at: "" }, { id: "category-2", name: "Salud", created_at: "", updated_at: "" }];
const item: PlanningPendingItem = { id: "pending-1", category_id: "category-1", category: { id: "category-1", name: "Personal" }, name: "Renovar documento", is_active: true, planned_date: "2026-08-20", progress: 20, state: "IN_PROGRESS", completion_date: null, compliance: null, detail_days: null, comment: "privado", lock_version: 7, created_at: "", updated_at: "" };
const page: PendingItemListResponse = { items: [item], total: 30, page: 1, page_size: 25, total_pages: 2 };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PlanningPendingItemsPage /></QueryClientProvider>);
  return client;
}

describe("PlanningPendingItemsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listAllCategoryOptions).mockResolvedValue(categories);
    vi.mocked(api.listPlanningPendingItems).mockResolvedValue(page);
    vi.mocked(api.createPlanningPendingItem).mockResolvedValue(item);
    vi.mocked(api.updatePlanningPendingItem).mockResolvedValue(item);
  });

  it("renders the Planning register without Tracking or deletion controls", async () => {
    renderPage();
    const register = await screen.findByRole("table", { name: "Registro de Pendientes" });
    expect(within(register).getByText("Renovar documento")).toBeInTheDocument();
    for (const heading of ["Vigencia", "Fecha planificada", "Pendiente", "Categoría", "Acciones"]) expect(within(register).getByRole("columnheader", { name: heading })).toBeInTheDocument();
    expect(screen.queryByText("privado")).not.toBeInTheDocument();
    expect(screen.queryByText("20")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /eliminar/i })).not.toBeInTheDocument();
  });

  it("requires a planned date for active creation", async () => {
    const user = userEvent.setup(); renderPage(); await screen.findByText("Renovar documento");
    const creation = screen.getByRole("heading", { name: "Crear Pendiente" }).closest<HTMLElement>("section")!;
    await user.selectOptions(within(creation).getByLabelText("Categoría"), "category-1");
    await user.type(within(creation).getByLabelText("Nombre"), "Comprar lentes");
    fireEvent.submit(within(creation).getByRole("button", { name: "Crear" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("requiere fecha planificada");
    expect(api.createPlanningPendingItem).not.toHaveBeenCalled();
  });

  it("creates an inactive item with an explicit null planned date", async () => {
    const user = userEvent.setup(); renderPage(); await screen.findByText("Renovar documento");
    const creation = screen.getByRole("heading", { name: "Crear Pendiente" }).closest<HTMLElement>("section")!;
    await user.selectOptions(within(creation).getByLabelText("Categoría"), "category-1");
    await user.type(within(creation).getByLabelText("Nombre"), "Comprar lentes");
    await user.selectOptions(within(creation).getByLabelText("Vigencia"), "inactive");
    await user.click(within(creation).getByRole("button", { name: "Crear" }));
    await waitFor(() => expect(api.createPlanningPendingItem).toHaveBeenCalledWith({ category_id: "category-1", name: "Comprar lentes", is_active: false, planned_date: null }));
  });

  it("uses server-driven filters and resets pagination for page-size changes", async () => {
    const user = userEvent.setup(); renderPage(); await screen.findByText("Renovar documento");
    const registerSection = screen.getByRole("heading", { name: "Registro de Pendientes" }).closest<HTMLElement>("section")!;
    await user.click(within(registerSection).getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(api.listPlanningPendingItems).toHaveBeenCalledWith(expect.objectContaining({ page: 2, page_size: 25 })));
    await user.selectOptions(within(registerSection).getByLabelText("Vigencia"), "false");
    await user.selectOptions(within(registerSection).getByLabelText("Categoría"), "category-2");
    await user.type(within(registerSection).getByLabelText("Desde"), "2026-08-01");
    await user.type(within(registerSection).getByLabelText("Hasta"), "2026-08-31");
    await waitFor(() => expect(api.listPlanningPendingItems).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 25, is_active: false, category_id: "category-2", planned_from: "2026-08-01", planned_to: "2026-08-31" })));
    const perPage = within(registerSection).getByLabelText("Por página");
    expect(within(perPage).getAllByRole("option").map((option) => option.textContent)).toEqual(["25", "50", "100"]);
    await user.selectOptions(perPage, "50");
    await waitFor(() => expect(api.listPlanningPendingItems).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 50 })));
  });

  it("shows a safe list error and retries the request", async () => {
    vi.mocked(api.listPlanningPendingItems).mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(page);
    const user = userEvent.setup(); renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar los Pendientes");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Renovar documento")).toBeInTheDocument();
  });

  it("edits only Planning fields, clears the date when deactivated and uses lock_version", async () => {
    const user = userEvent.setup(); renderPage(); await user.click(await screen.findByRole("button", { name: "Editar Renovar documento" }));
    await user.selectOptions(screen.getByLabelText("Categoría de Renovar documento"), "category-2");
    await user.clear(screen.getByLabelText("Nombre de Renovar documento")); await user.type(screen.getByLabelText("Nombre de Renovar documento"), "Renovar pasaporte");
    await user.selectOptions(screen.getByLabelText("Vigencia de Renovar documento"), "inactive");
    fireEvent.submit(screen.getByRole("button", { name: "Guardar Renovar documento" }).closest("form")!);
    await waitFor(() => expect(api.updatePlanningPendingItem).toHaveBeenCalledWith("pending-1", { category_id: "category-2", name: "Renovar pasaporte", is_active: false, planned_date: null, lock_version: 7 }));
  });

  it("requires a new date when reactivating an inactive item", async () => {
    vi.mocked(api.listPlanningPendingItems).mockResolvedValue({ ...page, items: [{ ...item, is_active: false, planned_date: null }] });
    const user = userEvent.setup(); renderPage(); await user.click(await screen.findByRole("button", { name: "Editar Renovar documento" }));
    await user.selectOptions(screen.getByLabelText("Vigencia de Renovar documento"), "active");
    fireEvent.submit(screen.getByRole("button", { name: "Guardar Renovar documento" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("requiere fecha planificada");
    expect(api.updatePlanningPendingItem).not.toHaveBeenCalled();
  });

  it("discards stale editing state after a 409", async () => {
    vi.mocked(api.updatePlanningPendingItem).mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
    const user = userEvent.setup(); renderPage(); await user.click(await screen.findByRole("button", { name: "Editar Renovar documento" }));
    await user.click(screen.getByRole("button", { name: "Guardar Renovar documento" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cambió desde la última carga");
    await waitFor(() => expect(screen.queryByLabelText("Nombre de Renovar documento")).not.toBeInTheDocument());
  });

  it("shows the neutral no-Categories state with no free-text fallback", async () => {
    vi.mocked(api.listAllCategoryOptions).mockResolvedValue([]); renderPage();
    expect(await screen.findByText("Aún no hay Categorías configuradas en Tablas > Categorías.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument();
  });
});
