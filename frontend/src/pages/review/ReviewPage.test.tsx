import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "../../api/queryKeys";
import * as reviewApi from "../../api/reviewApi";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { ReviewRead } from "../../types/review";
import { ReviewPage } from "./ReviewPage";

vi.mock("../../api/reviewApi", () => ({ getReview: vi.fn(), saveReview: vi.fn() }));

const review: ReviewRead = {
  review_date: "2026-08-13",
  last_review_saved_at: "2026-08-13T02:30:00Z",
  tasks: [
    { id: "task-1", planned_date: "2026-08-11", name: "Tender mi cama", lock_version: 2 },
    { id: "task-2", planned_date: "2026-08-13", name: "Beber agua", lock_version: 3 }
  ],
  pending_items: [
    { id: "pending-1", planned_date: "2026-08-10", name: "Renovar documento", progress: 20, comment: "En trámite", lock_version: 4 }
  ],
  projects: [
    { id: "project-1", name: "Mudanza", steps: [{ id: "step-1", planned_date: "2026-08-09", name: "Empacar", weight: "60.00", progress: 30, comment: null, lock_version: 5 }] },
    { id: "project-2", name: "Viaje", steps: [{ id: "step-2", planned_date: "2026-08-12", name: "Reservar", weight: "100.00", progress: 10, comment: "Cotizando", lock_version: 6 }] }
  ]
};

const auth: AuthState = {
  accessToken: "token", user: testUser, workspace: null,
  isAuthenticated: true, isInitializing: false,
  login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn()
};

function renderReview() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><AuthContext.Provider value={auth}><ReviewPage /></AuthContext.Provider></QueryClientProvider>);
  return client;
}

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reviewApi.getReview).mockResolvedValue(review);
    vi.mocked(reviewApi.saveReview).mockResolvedValue({ saved_at: "2026-08-13T20:00:00Z" });
  });

  it("renders the date, timestamp and compact target sections", async () => {
    renderReview();
    expect(await screen.findByRole("heading", { name: "Revisión", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("13 de agosto de 2026")).toBeInTheDocument();
    expect(screen.getByText(/12 ago\. 2026.*9:30 p\. m\./i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tareas" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pendientes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Proyectos" })).toBeInTheDocument();
  });

  it("keeps Task options in one row, accessible and local until Save", async () => {
    const user = userEvent.setup();
    renderReview();
    const taskName = await screen.findByText("Tender mi cama");
    const row = taskName.closest<HTMLElement>(".review-task-row")!;
    expect(within(row).getByRole("button", { name: "No realizado: Tender mi cama" })).toBeInTheDocument();
    const completed = within(row).getByRole("button", { name: "Completado: Tender mi cama" });
    await user.click(completed);
    expect(completed).toHaveAttribute("aria-pressed", "true");
    expect(reviewApi.saveReview).not.toHaveBeenCalled();
    expect(row).not.toHaveTextContent(/Categoría/i);
  });

  it("shows only approved Pending and Step fields grouped by Project", async () => {
    renderReview();
    await screen.findByText("Renovar documento");
    const pendingTable = screen.getByRole("table", { name: "Pendientes para revisión" });
    for (const label of ["Fecha planificada", "Pendiente", "Avance", "Comentario"]) expect(within(pendingTable).getByRole("columnheader", { name: label })).toBeInTheDocument();
    expect(screen.getByLabelText("Avance de Renovar documento")).toHaveValue(20);
    expect(screen.getByLabelText("Comentario de Renovar documento")).toHaveValue("En trámite");
    const mudanza = screen.getByRole("heading", { name: "Mudanza" }).closest("section")!;
    expect(within(mudanza).getByRole("table", { name: "Pasos de Mudanza" })).toHaveTextContent("Empacar");
    expect(screen.getByRole("heading", { name: "Viaje" })).toBeInTheDocument();
    expect(screen.queryByText(/Vigencia|Cumplimiento|Categoría|Comentario general/i)).not.toBeInTheDocument();
  });

  it("submits one exact batch, omits unselected/unchanged rows and refreshes Review and Home", async () => {
    const user = userEvent.setup();
    const client = renderReview();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    await user.click(await screen.findByRole("button", { name: "Completado: Tender mi cama" }));
    const pendingProgress = screen.getByLabelText("Avance de Renovar documento");
    await user.clear(pendingProgress); await user.type(pendingProgress, "45");
    await user.type(screen.getByLabelText("Comentario de Empacar"), "Terminado");
    expect(screen.getAllByRole("button", { name: "Guardar" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(reviewApi.saveReview).toHaveBeenCalledWith({
      tasks: [{ id: "task-1", result: "COMPLETED", lock_version: 2 }],
      pending_items: [{ id: "pending-1", progress: 45, lock_version: 4 }],
      project_steps: [{ id: "step-1", comment: "Terminado", lock_version: 5 }]
    }));
    await screen.findByText("Revisión guardada.");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.home });
    expect(reviewApi.getReview).toHaveBeenCalledTimes(2);
  });

  it("allows an empty Review save", async () => {
    vi.mocked(reviewApi.getReview).mockResolvedValue({ ...review, tasks: [], pending_items: [], projects: [], last_review_saved_at: null });
    const user = userEvent.setup(); renderReview();
    expect(await screen.findByText("No hay elementos que requieran revisión hoy.")).toBeInTheDocument();
    expect(screen.getByText("Sin registro")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(reviewApi.saveReview).toHaveBeenCalledWith({ tasks: [], pending_items: [], project_steps: [] });
  });

  it("preserves local edits after an atomic 409 and permits retry", async () => {
    vi.mocked(reviewApi.saveReview).mockRejectedValueOnce({ isAxiosError: true, response: { status: 409 } }).mockResolvedValueOnce({ saved_at: "2026-08-13T20:00:00Z" });
    const user = userEvent.setup(); renderReview();
    const progress = await screen.findByLabelText("Avance de Renovar documento");
    await user.clear(progress); await user.type(progress, "55");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Parte de la información cambió");
    expect(progress).toHaveValue(55);
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await screen.findByText("Revisión guardada.");
    expect(reviewApi.saveReview).toHaveBeenCalledTimes(2);
  });

  it("validates progress locally and performs no write", async () => {
    const user = userEvent.setup(); renderReview();
    const progress = await screen.findByLabelText("Avance de Renovar documento");
    await user.clear(progress); await user.type(progress, "101");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("entre 0 y 100");
    expect(reviewApi.saveReview).not.toHaveBeenCalled();
  });

  it("renders a stable loading state", () => {
    vi.mocked(reviewApi.getReview).mockReturnValueOnce(new Promise(() => undefined));
    renderReview();
    expect(screen.getByRole("status", { name: "Cargando Revisión" })).toBeInTheDocument();
    expect(screen.queryByText("Tender mi cama")).not.toBeInTheDocument();
  });

  it("renders a retryable GET error without fake rows", async () => {
    vi.mocked(reviewApi.getReview).mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(review);
    const user = userEvent.setup(); renderReview();
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar la Revisión.");
    expect(screen.queryByText("Tender mi cama")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Tender mi cama")).toBeInTheDocument();
  });
});
