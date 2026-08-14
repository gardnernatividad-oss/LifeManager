import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/taskReportApi";
import * as masters from "../../api/planningTaskApi";
import * as cats from "../../api/planningPendingItemApi";
import { TaskReportsPage } from "./TaskReportsPage";

vi.mock("../../api/taskReportApi", () => ({ getTaskReport: vi.fn() }));
vi.mock("../../api/planningTaskApi", () => ({ listAllMasterTasks: vi.fn() }));
vi.mock("../../api/planningPendingItemApi", () => ({ listAllCategoryOptions: vi.fn() }));

const category = { id: "c", name: "Actividad", created_at: "", updated_at: "" };
const master = {
  id: "m",
  name: "Correr",
  category_id: "c",
  category,
  created_at: "",
  updated_at: "",
};
const report = {
  period: { planned_from: null, planned_to: null },
  summary: {
    completed_count: 8,
    not_completed_count: 2,
    terminal_count: 10,
    completion_rate: "80.00",
  },
  by_master_task: [
    {
      master_task_id: "m",
      master_task_name: "Correr",
      category_id: "c",
      category_name: "Actividad",
      completed_count: 8,
      not_completed_count: 2,
      terminal_count: 10,
      completion_rate: "80.00",
    },
  ],
};

function mount() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <TaskReportsPage />
    </QueryClientProvider>,
  );
}

describe("TaskReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(masters.listAllMasterTasks).mockResolvedValue([master]);
    vi.mocked(cats.listAllCategoryOptions).mockResolvedValue([category]);
    vi.mocked(api.getTaskReport).mockResolvedValue(report);
  });

  it("renders authoritative summary and MasterTask breakdown read-only", async () => {
    mount();
    expect(await screen.findAllByText("80.00 %")).toHaveLength(2);
    for (const value of ["8", "2", "10", "Correr", "Actividad"])
      expect(screen.getAllByText(value).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /editar|eliminar|resultado|exportar/i })).not.toBeInTheDocument();
    expect(document.querySelector("svg,canvas")).toBeNull();
  });

  it("sends planned_from without planned_to", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findAllByText("80.00 %");
    await user.type(screen.getByLabelText("Desde"), "2026-08-01");
    await waitFor(() =>
      expect(api.getTaskReport).toHaveBeenCalledWith(
        expect.objectContaining({ planned_from: "2026-08-01" }),
      ),
    );
    expect(vi.mocked(api.getTaskReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_to");
  });

  it("sends planned_to without planned_from", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findAllByText("80.00 %");
    await user.type(screen.getByLabelText("Hasta"), "2026-08-31");
    await waitFor(() =>
      expect(api.getTaskReport).toHaveBeenCalledWith(
        expect.objectContaining({ planned_to: "2026-08-31" }),
      ),
    );
    expect(vi.mocked(api.getTaskReport).mock.calls.at(-1)?.[0]).not.toHaveProperty("planned_from");
  });

  it("sends all non-date filters and rejects reversed periods locally", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findAllByText("80.00 %");
    await user.selectOptions(screen.getByLabelText("Tarea"), "m");
    await user.selectOptions(screen.getByLabelText("Categoría"), "c");
    await user.type(screen.getByLabelText("Desde"), "2026-08-01");
    await user.type(screen.getByLabelText("Hasta"), "2026-07-01");
    expect(await screen.findByRole("alert")).toHaveTextContent("fecha Desde");
    const calls = vi.mocked(api.getTaskReport).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api.getTaskReport).toHaveBeenCalledTimes(calls);
  });

  it("shows zero counts, null rate and neutral empty message", async () => {
    vi.mocked(api.getTaskReport).mockResolvedValue({
      ...report,
      summary: {
        completed_count: 0,
        not_completed_count: 0,
        terminal_count: 0,
        completion_rate: null,
      },
      by_master_task: [],
    });
    mount();
    expect(await screen.findByText("No hay Tareas terminales para los filtros seleccionados.")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0.00 %")).not.toBeInTheDocument();
  });

  it("handles option errors with retry", async () => {
    vi.mocked(masters.listAllMasterTasks).mockRejectedValueOnce(new Error()).mockResolvedValueOnce([master]);
    const user = userEvent.setup();
    mount();
    expect(await screen.findByText("No pudimos cargar las opciones.")).toBeInTheDocument();
    expect(api.getTaskReport).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByLabelText("Tarea")).toBeInTheDocument();
    await waitFor(() => expect(api.getTaskReport).toHaveBeenCalledTimes(1));
  });

  it("shows the option loading state", () => {
    vi.mocked(masters.listAllMasterTasks).mockReturnValue(new Promise(() => {}));
    mount();
    expect(screen.getByText("Cargando opciones…")).toHaveAttribute("role", "status");
    expect(api.getTaskReport).not.toHaveBeenCalled();
  });

  it("handles report errors with retry", async () => {
    vi.mocked(api.getTaskReport).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(report);
    const user = userEvent.setup();
    mount();
    expect(await screen.findByText("No pudimos cargar el reporte.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findAllByText("80.00 %")).toHaveLength(2);
  });
});
