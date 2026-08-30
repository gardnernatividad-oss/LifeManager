import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as reviewApi from "../../api/reviewApi";
import type { ReviewRead } from "../../types/review";
import { ReviewPage } from "./ReviewPage";

vi.mock("../../api/reviewApi", () => ({ getReview: vi.fn(), saveReviewTasks: vi.fn(), saveReviewPendingItems: vi.fn(), saveReviewProjectStages: vi.fn() }));
const review: ReviewRead = {
  review_date: "2026-08-13",
  tasks: [{ id: "task-1", workspace_id: "ws-1", workspace_name: "Personal", planned_date: "2026-08-11", task_name: "Tender mi cama", lock_version: 2 }],
  pending_items: [{ id: "pending-1", workspace_id: "ws-1", workspace_name: "Personal", planned_date: "2026-08-10", pending_item_name: "Renovar documento", progress: 20, lock_version: 4 }],
  project_stages: [{ id: "stage-1", workspace_id: "ws-2", workspace_name: "Familia", planned_date: "2026-08-09", project_id: "project-1", project_name: "Mudanza", stage_name: "Empacar", progress: "30.00", lock_version: 5, project_lock_version: 7 }],
};
function renderReview() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ReviewPage /></QueryClientProvider>);
}

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks(); vi.mocked(reviewApi.getReview).mockResolvedValue(review);
    vi.mocked(reviewApi.saveReviewTasks).mockResolvedValue({ saved_ids: ["task-1"] });
    vi.mocked(reviewApi.saveReviewPendingItems).mockResolvedValue({ saved_ids: ["pending-1"] });
    vi.mocked(reviewApi.saveReviewProjectStages).mockResolvedValue({ saved_ids: ["stage-1"] });
  });
  it("renders three global collapsible blocks and counts without Workspace selector", async () => {
    renderReview(); expect(await screen.findByRole("heading", { name: "Revisión" })).toBeInTheDocument();
    expect(screen.getByText("Tareas").closest("details")).toHaveAttribute("open");
    expect(screen.getByLabelText("1 tareas")).toBeInTheDocument(); expect(screen.getByLabelText("1 pendientes")).toBeInTheDocument(); expect(screen.getByLabelText("1 etapas")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /workspace/i })).not.toBeInTheDocument();
  });
  it("preserves Pending and Stage drafts when Tasks save independently", async () => {
    const user = userEvent.setup(); renderReview();
    const pending = await screen.findByLabelText("Avance de Renovar documento"); const stage = screen.getByLabelText("Avance de Empacar");
    await user.clear(pending); await user.type(pending, "45"); await user.clear(stage); await user.type(stage, "55.25");
    await user.click(within(screen.getByRole("group", { name: "Resultado de Tender mi cama" })).getByRole("button", { name: "Completado" }));
    await user.click(screen.getByRole("button", { name: "Guardar Tareas" }));
    await waitFor(() => expect(vi.mocked(reviewApi.saveReviewTasks).mock.calls[0]?.[0]).toEqual({ items: [{ task_id: "task-1", result: "COMPLETED", lock_version: 2 }] }));
    expect(reviewApi.saveReviewPendingItems).not.toHaveBeenCalled(); expect(reviewApi.saveReviewProjectStages).not.toHaveBeenCalled();
    expect(pending).toHaveValue(45); expect(stage).toHaveValue(55.25);
  });
  it("keeps a draft across collapse and generic/conflict errors", async () => {
    vi.mocked(reviewApi.saveReviewPendingItems).mockRejectedValueOnce(new Error("network"));
    vi.mocked(reviewApi.saveReviewProjectStages).mockRejectedValueOnce({ isAxiosError: true, response: { status: 409 } });
    const user = userEvent.setup(); renderReview(); const pending = await screen.findByLabelText("Avance de Renovar documento");
    await user.clear(pending); await user.type(pending, "61"); await user.click(screen.getByText("Pendientes")); await user.click(screen.getByText("Pendientes"));
    expect(pending).toHaveValue(61); await user.click(screen.getByRole("button", { name: "Guardar Pendientes" }));
    expect(await screen.findByText(/Tus cambios siguen disponibles/)).toBeInTheDocument(); expect(pending).toHaveValue(61);
    const stage = screen.getByLabelText("Avance de Empacar"); await user.clear(stage); await user.type(stage, "62.50"); await user.click(screen.getByRole("button", { name: "Guardar Proyectos" }));
    expect(await screen.findByText(/conservamos tus cambios/)).toBeInTheDocument(); expect(stage).toHaveValue(62.5);
  });
  it("sends exact Pending and Decimal Stage contracts", async () => {
    const user = userEvent.setup(); renderReview(); await screen.findByText("Renovar documento");
    const pending = screen.getByLabelText("Avance de Renovar documento"); await user.clear(pending); await user.type(pending, "40"); await user.type(screen.getByLabelText("Comentario de Renovar documento"), "Avancé");
    await user.click(screen.getByRole("button", { name: "Guardar Pendientes" }));
    await waitFor(() => expect(vi.mocked(reviewApi.saveReviewPendingItems).mock.calls[0]?.[0]).toEqual({ items: [{ pending_item_id: "pending-1", progress: 40, comment: "Avancé", lock_version: 4 }] }));
    const stage = screen.getByLabelText("Avance de Empacar"); await user.clear(stage); await user.type(stage, "42.25"); await user.click(screen.getByRole("button", { name: "Guardar Proyectos" }));
    await waitFor(() => expect(vi.mocked(reviewApi.saveReviewProjectStages).mock.calls[0]?.[0]).toEqual({ items: [{ stage_id: "stage-1", progress: "42.25", lock_version: 5, project_lock_version: 7 }] }));
  });
  it("renders independent empty states", async () => {
    vi.mocked(reviewApi.getReview).mockResolvedValueOnce({ review_date: "2026-08-13", tasks: [], pending_items: [], project_stages: [] }); renderReview();
    expect(await screen.findByText("No tienes tareas pendientes para revisar.")).toBeInTheDocument(); expect(screen.getByText("No tienes pendientes para revisar.")).toBeInTheDocument(); expect(screen.getByText("No tienes etapas para revisar.")).toBeInTheDocument();
  });
});
