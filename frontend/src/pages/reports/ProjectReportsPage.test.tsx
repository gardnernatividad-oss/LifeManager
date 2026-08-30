import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as categoryApi from "../../api/planningPendingItemApi";
import * as reportApi from "../../api/projectReportApi";
import type { ProjectReportResponse } from "../../types/projectReport";
import { ProjectReportsPage } from "./ProjectReportsPage";

vi.mock("../../api/projectReportApi", () => ({ getProjectReport: vi.fn() }));
vi.mock("../../api/planningPendingItemApi", () => ({ listAllCategoryOptions: vi.fn() }));

const category = { id: "category-id", name: "Personal", created_at: "", updated_at: "" };
const report: ProjectReportResponse = {
  period: { planned_from: null, planned_to: null },
  filters: { category_id: null, is_active: null, state: null },
  summary: {
    total_count: 6, active_count: 4, inactive_count: 2,
    no_iniciado_count: 1, en_proceso_count: 3, finalizado_count: 2,
  },
  step_compliance: {
    en_plazo_count: 7, atrasado_count: 5, con_adelanto_count: 4,
    a_tiempo_count: 3, con_retraso_count: 2,
  },
  detail: {
    average_atrasado_days: "3.25",
    average_con_adelanto_days: "2.50",
    average_con_retraso_days: "4.75",
  },
  by_project: [{
    project_id: "project-id", project_name: "Mudanza", category_id: "category-id",
    category_name: "Personal", is_active: true, planned_date: "2026-09-30",
    progress: "75.00", state: "EN_PROCESO", step_count: 8,
  }],
};

function mount() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ProjectReportsPage />
    </QueryClientProvider>,
  );
}

describe("ProjectReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(categoryApi.listAllCategoryOptions).mockResolvedValue([category]);
    vi.mocked(reportApi.getProjectReport).mockResolvedValue(report);
  });

  it("renders backend Project summary and clearly Step-level analytics", async () => {
    mount();
    expect(await screen.findByText("3.25")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cumplimiento de Etapas" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Detalle de Etapas" })).toBeInTheDocument();
    for (const label of [
      "Total", "Activos", "Inactivos", "No iniciados", "En proceso", "Finalizados",
      "En plazo", "Atrasados", "Con adelanto", "A tiempo", "Con retraso",
      "Promedio de días de atraso", "Promedio de días de adelanto", "Promedio de días de retraso",
    ]) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  });

  it("renders the authoritative Project breakdown without Project Compliance or actions", async () => {
    mount();
    expect(await screen.findByRole("table", { name: "Resultados por proyecto" })).toBeInTheDocument();
    for (const value of ["Mudanza", "Personal", "Activo", "30/09/2026", "75.00 %", "En proceso", "8"])
      expect(screen.getAllByText(value).length).toBeGreaterThan(0);
    expect(screen.queryByRole("columnheader", { name: /cumplimiento/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /abrir|ver|editar|eliminar|guardar|exportar|tracking|planificación/i })).not.toBeInTheDocument();
    expect(document.querySelector("svg,canvas")).toBeNull();
  });

  it("sends planned_from without planned_to", async () => {
    const user = userEvent.setup(); mount(); await screen.findByText("3.25");
    await user.type(screen.getByLabelText("Desde"), "2026-08-01");
    await waitFor(() => expect(reportApi.getProjectReport).toHaveBeenCalledWith(expect.objectContaining({ planned_from: "2026-08-01" })));
    expect(vi.mocked(reportApi.getProjectReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_to");
  });

  it("sends planned_to without planned_from", async () => {
    const user = userEvent.setup(); mount(); await screen.findByText("3.25");
    await user.type(screen.getByLabelText("Hasta"), "2026-08-31");
    await waitFor(() => expect(reportApi.getProjectReport).toHaveBeenCalledWith(expect.objectContaining({ planned_to: "2026-08-31" })));
    expect(vi.mocked(reportApi.getProjectReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_from");
  });

  it("sends Category, Vigencia and State filters", async () => {
    const user = userEvent.setup(); mount(); await screen.findByText("3.25");
    await user.selectOptions(screen.getByLabelText("Categoría"), "category-id");
    await user.selectOptions(screen.getByLabelText("Vigencia"), "false");
    await user.selectOptions(screen.getByLabelText("Estado"), "FINALIZADO");
    await waitFor(() => expect(reportApi.getProjectReport).toHaveBeenCalledWith({
      category_id: "category-id", is_active: false, state: "FINALIZADO",
    }));
  });

  it("suppresses requests for a reversed period", async () => {
    const user = userEvent.setup(); mount(); await screen.findByText("3.25");
    await user.type(screen.getByLabelText("Desde"), "2026-08-31");
    await user.type(screen.getByLabelText("Hasta"), "2026-08-01");
    expect(await screen.findByRole("alert")).toHaveTextContent("fecha Desde");
    const calls = vi.mocked(reportApi.getProjectReport).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(reportApi.getProjectReport).toHaveBeenCalledTimes(calls);
  });

  it("suppresses reports while Categories fail and enables after retry", async () => {
    vi.mocked(categoryApi.listAllCategoryOptions).mockRejectedValueOnce(new Error()).mockResolvedValueOnce([category]);
    const user = userEvent.setup(); mount();
    expect(await screen.findByText("No pudimos cargar las categorías.")).toBeInTheDocument();
    expect(reportApi.getProjectReport).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(reportApi.getProjectReport).toHaveBeenCalledTimes(1));
  });

  it("suppresses reports while Categories load", () => {
    vi.mocked(categoryApi.listAllCategoryOptions).mockReturnValue(new Promise(() => {}));
    mount();
    expect(screen.getByText("Cargando categorías…")).toHaveAttribute("role", "status");
    expect(reportApi.getProjectReport).not.toHaveBeenCalled();
  });

  it("renders null Project progress, State and date without inference", async () => {
    vi.mocked(reportApi.getProjectReport).mockResolvedValue({
      ...report,
      by_project: [{ ...report.by_project[0], planned_date: null, progress: null, state: null }],
    });
    mount(); await screen.findByRole("table");
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByText("0.00 %")).not.toBeInTheDocument();
  });

  it("renders empty reports and null Step averages neutrally", async () => {
    vi.mocked(reportApi.getProjectReport).mockResolvedValue({
      ...report,
      summary: { total_count: 0, active_count: 0, inactive_count: 0, no_iniciado_count: 0, en_proceso_count: 0, finalizado_count: 0 },
      detail: { average_atrasado_days: null, average_con_adelanto_days: null, average_con_retraso_days: null },
      by_project: [],
    });
    mount();
    expect(await screen.findByText("No hay Proyectos para los filtros seleccionados.")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("handles report errors with retry without fake metrics", async () => {
    vi.mocked(reportApi.getProjectReport).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(report);
    const user = userEvent.setup(); mount();
    expect(await screen.findByText("No pudimos cargar el reporte.")).toBeInTheDocument();
    expect(screen.queryByText("3.25")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("3.25")).toBeInTheDocument();
  });
});
