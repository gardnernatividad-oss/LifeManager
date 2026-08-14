import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as reportApi from "../../api/pendingItemReportApi";
import * as categoryApi from "../../api/planningPendingItemApi";
import type { PendingItemReportResponse } from "../../types/pendingItemReport";
import { PendingItemReportsPage } from "./PendingItemReportsPage";

vi.mock("../../api/pendingItemReportApi", () => ({ getPendingItemReport: vi.fn() }));
vi.mock("../../api/planningPendingItemApi", () => ({ listAllCategoryOptions: vi.fn() }));

const category = { id: "category-id", name: "Personal", created_at: "", updated_at: "" };
const report: PendingItemReportResponse = {
  period: { planned_from: null, planned_to: null },
  filters: { category_id: null, is_active: null, state: null, compliance: null },
  summary: {
    total_count: 12,
    active_count: 8,
    inactive_count: 4,
    no_iniciado_count: 3,
    en_proceso_count: 5,
    finalizado_count: 4,
  },
  compliance: {
    en_plazo_count: 2,
    atrasado_count: 3,
    con_adelanto_count: 4,
    a_tiempo_count: 1,
    con_retraso_count: 2,
  },
  detail: {
    average_atrasado_days: "3.50",
    average_con_adelanto_days: "2.25",
    average_con_retraso_days: "4.75",
  },
  by_category: [
    {
      category_id: "category-id",
      category_name: "Personal",
      summary: {
        total_count: 12,
        active_count: 8,
        inactive_count: 4,
        no_iniciado_count: 3,
        en_proceso_count: 5,
        finalizado_count: 4,
      },
      compliance: {
        en_plazo_count: 2,
        atrasado_count: 3,
        con_adelanto_count: 4,
        a_tiempo_count: 1,
        con_retraso_count: 2,
      },
    },
  ],
};

function mount() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PendingItemReportsPage />
    </QueryClientProvider>,
  );
}

describe("PendingItemReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(categoryApi.listAllCategoryOptions).mockResolvedValue([category]);
    vi.mocked(reportApi.getPendingItemReport).mockResolvedValue(report);
  });

  it("renders backend summary, compliance, detail and Category breakdown read-only", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Reportes · Pendientes" })).toBeInTheDocument();
    await screen.findByText("3.50");
    for (const label of [
      "Total", "Activos", "Inactivos", "No iniciados", "En proceso", "Finalizados",
      "En plazo", "Atrasados", "Con adelanto", "A tiempo", "Con retraso",
      "Promedio de días de atraso", "Promedio de días de adelanto", "Promedio de días de retraso",
    ]) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    for (const value of ["3.50", "2.25", "4.75", "Personal"])
      expect(screen.getAllByText(value).length).toBeGreaterThan(0);
    expect(screen.getByRole("table", { name: "Resultados por categoría" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar|eliminar|guardar|exportar|tracking|planificación/i })).not.toBeInTheDocument();
    expect(document.querySelector("svg,canvas")).toBeNull();
  });

  it("sends planned_from without planned_to", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("3.50");
    await user.type(screen.getByLabelText("Desde"), "2026-08-01");
    await waitFor(() => expect(reportApi.getPendingItemReport).toHaveBeenCalledWith(
      expect.objectContaining({ planned_from: "2026-08-01" }),
    ));
    expect(vi.mocked(reportApi.getPendingItemReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_to");
  });

  it("sends planned_to without planned_from", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("3.50");
    await user.type(screen.getByLabelText("Hasta"), "2026-08-31");
    await waitFor(() => expect(reportApi.getPendingItemReport).toHaveBeenCalledWith(
      expect.objectContaining({ planned_to: "2026-08-31" }),
    ));
    expect(vi.mocked(reportApi.getPendingItemReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_from");
  });

  it("sends Category, Vigencia, State and Compliance filters", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("3.50");
    await user.selectOptions(screen.getByLabelText("Categoría"), "category-id");
    await user.selectOptions(screen.getByLabelText("Vigencia"), "false");
    await user.selectOptions(screen.getByLabelText("Estado"), "EN_PROCESO");
    await user.selectOptions(screen.getByLabelText("Cumplimiento"), "ATRASADO");
    await waitFor(() => expect(reportApi.getPendingItemReport).toHaveBeenCalledWith({
      category_id: "category-id",
      is_active: false,
      state: "EN_PROCESO",
      compliance: "ATRASADO",
    }));
  });

  it("suppresses requests for a reversed period", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("3.50");
    await user.type(screen.getByLabelText("Desde"), "2026-08-31");
    await user.type(screen.getByLabelText("Hasta"), "2026-08-01");
    expect(await screen.findByRole("alert")).toHaveTextContent("fecha Desde");
    const calls = vi.mocked(reportApi.getPendingItemReport).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(reportApi.getPendingItemReport).toHaveBeenCalledTimes(calls);
  });

  it("suppresses report loading while Categories load or fail and enables it after retry", async () => {
    vi.mocked(categoryApi.listAllCategoryOptions)
      .mockRejectedValueOnce(new Error())
      .mockResolvedValueOnce([category]);
    const user = userEvent.setup();
    mount();
    expect(await screen.findByText("No pudimos cargar las categorías.")).toBeInTheDocument();
    expect(reportApi.getPendingItemReport).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(reportApi.getPendingItemReport).toHaveBeenCalledTimes(1));
  });

  it("suppresses the report request while Category options are loading", () => {
    vi.mocked(categoryApi.listAllCategoryOptions).mockReturnValue(new Promise(() => {}));
    mount();
    expect(screen.getByText("Cargando categorías…")).toHaveAttribute("role", "status");
    expect(reportApi.getPendingItemReport).not.toHaveBeenCalled();
  });

  it("renders empty results and null averages without fabricated values", async () => {
    vi.mocked(reportApi.getPendingItemReport).mockResolvedValue({
      ...report,
      summary: {
        total_count: 0, active_count: 0, inactive_count: 0,
        no_iniciado_count: 0, en_proceso_count: 0, finalizado_count: 0,
      },
      detail: {
        average_atrasado_days: null,
        average_con_adelanto_days: null,
        average_con_retraso_days: null,
      },
      by_category: [],
    });
    mount();
    expect(await screen.findByText("No hay Pendientes para los filtros seleccionados.")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("handles report errors with retry without fake metrics", async () => {
    vi.mocked(reportApi.getPendingItemReport).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(report);
    const user = userEvent.setup();
    mount();
    expect(await screen.findByText("No pudimos cargar el reporte.")).toBeInTheDocument();
    expect(screen.queryByText("3.50")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("3.50")).toBeInTheDocument();
  });
});
