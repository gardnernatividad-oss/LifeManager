import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/v2PendingItemApi";
import { PendingItemDetailPage } from "./PendingItemDetailPage";

vi.mock("../../api/v2PendingItemApi", () => ({ getV2PendingItem: vi.fn(), listV2PendingItemHistory: vi.fn(), updateV2PendingItemProgress: vi.fn(), correctV2PendingItem: vi.fn(), deactivateV2PendingItem: vi.fn(), reactivateV2PendingItem: vi.fn(), deleteV2PendingItem: vi.fn() }));
const auth = { workspace: { id: "workspace-a", name: "Familia", kind: "SHARED", timezone: "America/Lima" } };
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));
const item = { id: "pending-1", workspace_id: "workspace-a", category_id: "category-1", category_name: "Casa", responsible_user_id: "user-1", responsible_display_name: "Ana Uno", responsible_email: "ana@example.com", name: "Renovar documento", is_active: true, planned_date: "2026-08-20", progress: 40, state: "EN_PROCESO" as const, completion_date: null, compliance: "ATRASADO" as const, compliance_detail_days: 6, lock_version: 7, can_edit: true, can_update_progress: true, can_correct: false, can_deactivate: true, can_reactivate: false, can_delete: false, created_at: "", updated_at: "" };
const history = { items: [{ id: "history-1", progress: 40, comment: "Información recibida", type: "TRACKING" as const, actor_user_id: "user-1", actor_display_name: "Ana Uno", recorded_at: "2026-08-26T20:00:00Z" }] };

function renderPage() { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/planificacion/pendientes/pending-1"]}><Routes><Route path="/planificacion/pendientes/:pendingItemId" element={<PendingItemDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>); }

describe("V2 PendingItemDetailPage", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.getV2PendingItem).mockResolvedValue(item); vi.mocked(api.listV2PendingItemHistory).mockResolvedValue(history); vi.mocked(api.updateV2PendingItemProgress).mockResolvedValue(item); vi.mocked(api.correctV2PendingItem).mockResolvedValue(item); });

  it("shows the full detail and newest-first history projection", async () => { renderPage(); expect(await screen.findByRole("heading", { name: "Renovar documento" })).toBeInTheDocument(); expect(screen.getAllByText("40%").length).toBeGreaterThan(0); expect(screen.getByText("Información recibida")).toBeInTheDocument(); expect(screen.getAllByText("Seguimiento").length).toBeGreaterThan(0); expect(screen.getByRole("link", { name: "Volver al registro de Pendientes" })).toBeInTheDocument(); });

  it("saves a comment without inventing a progress change", async () => { const user = userEvent.setup(); renderPage(); await screen.findByText("Información recibida"); await user.type(screen.getByLabelText("Comentario (opcional)"), "Nueva evidencia"); await user.click(screen.getByRole("button", { name: "Guardar seguimiento" })); await waitFor(() => expect(api.updateV2PendingItemProgress).toHaveBeenCalledWith("workspace-a", "pending-1", null, 7, "Nueva evidencia")); });

  it("saves progress and comment as one request", async () => { const user = userEvent.setup(); renderPage(); await screen.findByText("Información recibida"); await user.type(screen.getByLabelText("Avance (opcional)"), "60"); await user.type(screen.getByLabelText("Comentario (opcional)"), "Segundo avance"); await user.click(screen.getByRole("button", { name: "Guardar seguimiento" })); await waitFor(() => expect(api.updateV2PendingItemProgress).toHaveBeenCalledWith("workspace-a", "pending-1", 60, 7, "Segundo avance")); });

  it("keeps finalized items read-only and exposes explicit correction", async () => { vi.mocked(api.getV2PendingItem).mockResolvedValue({ ...item, progress: 100, state: "FINALIZADO", completion_date: "2026-08-25", can_edit: false, can_update_progress: false, can_correct: true, can_deactivate: false }); const user = userEvent.setup(); renderPage(); expect(await screen.findByRole("heading", { name: "Corrección" })).toBeInTheDocument(); expect(screen.queryByText("Editar planificación")).not.toBeInTheDocument(); await user.type(screen.getByLabelText("Nuevo avance"), "80"); await user.type(screen.getByLabelText("Comentario (opcional)"), "Corrección validada"); await user.click(screen.getByRole("button", { name: "Guardar seguimiento" })); await waitFor(() => expect(api.correctV2PendingItem).toHaveBeenCalledWith("workspace-a", "pending-1", 80, 7, "Corrección validada")); });

  it("does not render comments as HTML", async () => { vi.mocked(api.listV2PendingItemHistory).mockResolvedValue({ items: [{ ...history.items[0], comment: "<script>alert(1)</script>" }] }); renderPage(); expect(await screen.findByText("<script>alert(1)</script>")).toBeInTheDocument(); expect(document.querySelector("script")).toBeNull(); });
});
