import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as projectApi from "../../api/v2ProjectApi";
import * as stageApi from "../../api/v2ProjectStageApi";
import { V2ProjectDetailPage } from "./V2ProjectDetailPage";
import { V2ProjectStageDetailPage } from "./V2ProjectStageDetailPage";

vi.mock("../../api/v2ProjectApi", () => ({ getV2Project: vi.fn() }));
vi.mock("../../api/v2ProjectStageApi", () => ({ listV2ProjectStages: vi.fn(), getV2ProjectStage: vi.fn(), listV2ProjectStageHistory: vi.fn(), updateV2ProjectStageProgress: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({ listWorkspaceMembers: vi.fn().mockResolvedValue([]) }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ workspace: { id: "workspace-a", name: "Familia", kind: "SHARED", timezone: "America/Lima" } }) }));

const project = { id: "project-1", workspace_id: "workspace-a", category_id: "category-1", category_name: "Casa", leader_user_id: "user-1", leader_display_name: "Ana Uno", leader_email: "ana@example.com", name: "Mudanza", description: "Plan familiar", is_active: true, planned_date: "2026-09-10", progress: 20, state: "EN_PROCESO", compliance: "EN_PLAZO", compliance_detail_days: 5, completion_date: null, weights_complete: true, stage_count: 1, total_weight: "100", lock_version: 4, can_edit: true, can_deactivate: true, can_reactivate: false, created_at: "", updated_at: "" };
const stage = { id: "stage-1", workspace_id: "workspace-a", project_id: "project-1", responsible_user_id: "user-2", responsible_display_name: "Luis Dos", responsible_email: "luis@example.com", name: "Empacar", position: 0, weight: "100.00", planned_date: "2026-09-10", progress: 20, state: "EN_PROCESO" as const, completion_date: null, compliance: "EN_PLAZO" as const, compliance_detail_days: 5, lock_version: 2, can_edit: true, can_update_progress: true, created_at: "", updated_at: "" };

function mount(path: string, element: ReactNode) { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}><Routes><Route path="/seguimiento/proyectos/:projectId" element={element} /><Route path="/seguimiento/proyectos/:projectId/etapas/:stageId" element={element} /></Routes></QueryClientProvider></MemoryRouter>); }

describe("V2 Project hierarchical detail", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(projectApi.getV2Project).mockResolvedValue(project); vi.mocked(stageApi.listV2ProjectStages).mockResolvedValue({ items: [stage], total_weight: "100", weights_complete: true }); vi.mocked(stageApi.getV2ProjectStage).mockResolvedValue(stage); vi.mocked(stageApi.listV2ProjectStageHistory).mockResolvedValue({ items: [{ id: "history-1", progress: 20, comment: "Empezamos", type: "TRACKING", actor_user_id: "user-1", actor_display_name: "Ana Uno", recorded_at: "2026-09-01T12:00:00Z" }] }); vi.mocked(stageApi.updateV2ProjectStageProgress).mockResolvedValue({ ...stage, progress: 30, lock_version: 3 }); });

  it("shows Project fields and a scoped Stage link", async () => { mount("/seguimiento/proyectos/project-1", <V2ProjectDetailPage mode="tracking" />); expect(await screen.findByRole("heading", { name: "Mudanza" })).toBeInTheDocument(); expect(screen.getByText("Plan familiar")).toBeInTheDocument(); expect(await screen.findByRole("link", { name: "Abrir Etapa Empacar" })).toHaveAttribute("href", "/seguimiento/proyectos/project-1/etapas/stage-1"); expect(screen.getByRole("link", { name: "← Volver a Proyectos" })).toHaveAttribute("href", "/seguimiento/proyectos"); });

  it("shows history and saves progress plus comment atomically", async () => { const user = userEvent.setup(); mount("/seguimiento/proyectos/project-1/etapas/stage-1", <V2ProjectStageDetailPage mode="tracking" />); expect(await screen.findByRole("heading", { name: "Empacar" })).toBeInTheDocument(); expect(await screen.findByText("Empezamos")).toBeInTheDocument(); await user.type(screen.getByLabelText("Nuevo avance (%)"), "30"); await user.type(screen.getByLabelText("Comentario"), "Cajas listas"); await user.click(screen.getByRole("button", { name: "Guardar seguimiento" })); await waitFor(() => expect(stageApi.updateV2ProjectStageProgress).toHaveBeenCalledWith("workspace-a", "project-1", "stage-1", { progress: 30, comment: "Cajas listas", lock_version: 2, project_lock_version: 4 })); });

  it("supports comment-only and clears hierarchy state on Workspace remount", async () => { const user = userEvent.setup(); mount("/seguimiento/proyectos/project-1/etapas/stage-1", <V2ProjectStageDetailPage mode="tracking" />); await screen.findByRole("heading", { name: "Empacar" }); await user.type(screen.getByLabelText("Comentario"), "Sin cambio"); await user.click(screen.getByRole("button", { name: "Guardar seguimiento" })); await waitFor(() => expect(stageApi.updateV2ProjectStageProgress).toHaveBeenCalledWith("workspace-a", "project-1", "stage-1", { comment: "Sin cambio", lock_version: 2, project_lock_version: 4 })); });
});
