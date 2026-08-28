import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/v2ActivityApi";
import * as workspaceApi from "../../api/workspaceApi";
import { PlanningActivitiesPage } from "./PlanningActivitiesPage";

vi.mock("../../api/v2ActivityApi", () => ({ listV2Activities: vi.fn(), createV2Activity: vi.fn(), createRecurringV2Activities: vi.fn(), updateV2Activity: vi.fn(), deleteV2Activity: vi.fn(), leaveV2Activity: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({ listWorkspaceMembers: vi.fn() }));
vi.mock("../../components/common/V2CatalogSelector", () => ({ ActivityCatalogSelector: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => <label>Actividad<select value={value} onChange={(event) => onChange(event.target.value)}><option value="">Selecciona</option><option value="master-1">Reunión</option></select></label> }));
const auth = { user: { id: "user-1", email: "ana@example.com", first_name: "Ana", last_name: "Uno", timezone: "America/Lima" }, workspace: { id: "workspace-a", name: "Familia", kind: "SHARED" as "SHARED" | "PERSONAL", timezone: "America/Lima" } };
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));
const base = { id: "activity-1", workspace_id: "workspace-a", activity_master_id: "master-1", activity_master_name: "Reunión", category_id: "category-1", category_name: "Familia", title: "Reunión", organizer_user_id: "user-1", organizer_display_name: "Ana Uno", organizer_email: "ana@example.com", participants: [{ user_id: "user-2", display_name: "Luis Dos", email: "luis@example.com", calendar_status: "VISIBLE" as const }], starts_at: "2027-01-01T15:00:00Z", ends_at: "2027-01-01T16:00:00Z", status: "SCHEDULED" as const, temporal_state: "FUTURE" as const, lock_version: 2, is_generated: false, can_edit: true, can_delete: true, can_leave_participation: false, created_at: "", updated_at: "" };
function mount() { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return render(<QueryClientProvider client={client}><PlanningActivitiesPage /></QueryClientProvider>); }

describe("PlanningActivitiesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks(); auth.workspace = { id: "workspace-a", name: "Familia", kind: "SHARED", timezone: "America/Lima" };
    vi.mocked(workspaceApi.listWorkspaceMembers).mockResolvedValue([{ user_id: "user-1", display_name: "Ana Uno", email: "ana@example.com", role: "Miembro", status: "ACTIVE", joined_at: "", ended_at: null }, { user_id: "user-2", display_name: "Luis Dos", email: "luis@example.com", role: "Miembro", status: "ACTIVE", joined_at: "", ended_at: null }]);
    vi.mocked(api.listV2Activities).mockResolvedValue({ items: [base], total: 1, page: 1, page_size: 25, total_pages: 1 });
    vi.mocked(api.createV2Activity).mockResolvedValue(base); vi.mocked(api.createRecurringV2Activities).mockResolvedValue({ created_count: 1, items: [base] }); vi.mocked(api.updateV2Activity).mockResolvedValue(base); vi.mocked(api.deleteV2Activity).mockResolvedValue(); vi.mocked(api.leaveV2Activity).mockResolvedValue(base);
  });
  it("creates a Shared Activity with organizer, participants and timezone-aware instants", async () => {
    const user = userEvent.setup(); mount(); const form = screen.getByRole("heading", { name: "Crear Actividad" }).closest("section")!;
    await user.selectOptions(within(form).getByLabelText("Actividad"), "master-1"); await user.selectOptions(within(form).getByLabelText("Organizador"), "user-1");
    await user.type(within(form).getByLabelText("Inicio"), "2027-01-01T10:00"); await user.type(within(form).getByLabelText("Fin"), "2027-01-01T11:00"); await user.click(within(form).getByLabelText("Luis Dos")); await user.click(within(form).getByRole("button", { name: "Crear" }));
    await waitFor(() => expect(api.createV2Activity).toHaveBeenCalledWith("workspace-a", expect.objectContaining({ activity_master_id: "master-1", organizer_user_id: "user-1", participant_user_ids: ["user-2"], starts_at: "2027-01-01T15:00:00.000Z", ends_at: "2027-01-01T16:00:00.000Z" })));
  });
  it("creates a finite recurring Activity in the Workspace timezone", async () => {
    const user = userEvent.setup(); mount(); const form = screen.getByRole("heading", { name: "Crear Actividad" }).closest("section")!;
    await user.click(within(form).getByLabelText("Repetir")); await user.selectOptions(within(form).getByLabelText("Actividad"), "master-1"); await user.selectOptions(within(form).getByLabelText("Organizador"), "user-1");
    await user.type(within(form).getByLabelText("Desde"), "2027-01-01"); await user.type(within(form).getByLabelText("Hasta"), "2027-01-02"); await user.type(within(form).getByLabelText("Hora de inicio"), "09:00"); await user.type(within(form).getByLabelText("Hora de fin"), "10:00"); await user.click(within(form).getByRole("button", { name: "Crear" }));
    await waitFor(() => expect(api.createRecurringV2Activities).toHaveBeenCalledWith("workspace-a", expect.objectContaining({ timezone: "America/Lima", recurrence: expect.objectContaining({ pattern: "DAILY", date_from: "2027-01-01", date_until: "2027-01-02" }) })));
  });
  it("renders only server-authorized future actions and keeps started Activities read-only", async () => {
    vi.mocked(api.listV2Activities).mockResolvedValue({ items: [{ ...base, temporal_state: "IN_PROGRESS", can_edit: false, can_delete: false, can_leave_participation: false }], total: 1, page: 1, page_size: 25, total_pages: 1 });
    mount(); expect(await screen.findByText("En curso")).toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Eliminar" })).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Retirarme" })).not.toBeInTheDocument();
  });
  it("offers occurrence scopes only for generated Activities", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listV2Activities).mockResolvedValue({ items: [{ ...base, is_generated: true }], total: 1, page: 1, page_size: 25, total_pages: 1 });
    mount();
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("heading", { name: "Cancelar Actividad" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Esta y todas las futuras" }));
    await waitFor(() => expect(api.deleteV2Activity).toHaveBeenCalledWith("workspace-a", "activity-1", 2, "THIS_AND_FUTURE"));
  });
  it("does not offer a future scope selector for standalone Activities", async () => {
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(api.deleteV2Activity).toHaveBeenCalledWith("workspace-a", "activity-1", 2));
    expect(screen.queryByRole("button", { name: "Esta y todas las futuras" })).not.toBeInTheDocument();
  });
  it("derives Personal organizer and hides collaborative participants", async () => {
    auth.workspace = { id: "personal-a", name: "Personal", kind: "PERSONAL", timezone: "America/Lima" }; mount();
    expect(screen.getByText("Organizador: tú")).toBeInTheDocument(); expect(screen.queryByRole("group", { name: "Participantes" })).not.toBeInTheDocument();
  });
});
