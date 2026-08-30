import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as homeApi from "../../api/homeApi";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { V2HomeSummary } from "../../types/v2Home";
import { HomePage } from "./HomePage";

vi.mock("../../api/homeApi", () => ({ getV2HomeSummary: vi.fn() }));
const workspace = { id: "workspace-a", name: "Personal", color: "BLUE", icon: "HOME" };
const summary: V2HomeSummary = { local_date: "2026-08-30", today: { tasks: 1, pending_items: 2, project_stages: 3, activities: 4 }, upcoming_activities: [{ id: "activity-a", name: "Consulta", starts_at: "2026-08-31T15:00:00Z", ends_at: "2026-08-31T16:00:00Z", workspace }], attention: [{ type: "PROJECT_STAGE", id: "stage-a", project_id: "project-a", name: "Mudanza · Empacar", planned_date: "2026-08-20", workspace }], upcoming_days: Array.from({ length: 7 }, (_, index) => ({ date: `2026-09-0${index + 1}`, tasks: index, pending_items: 0, project_stages: 0, activities: 1 })) };
const auth: AuthState = { user: testUser, workspace: null, isAuthenticated: true, isInitializing: false, login: vi.fn(), logout: vi.fn(), setWorkspace: vi.fn(), clearSession: vi.fn(), setAuthenticatedUser: vi.fn() };
function mount() { return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthContext.Provider value={auth}><HomePage /></AuthContext.Provider></QueryClientProvider></MemoryRouter>); }

describe("V2 HomePage", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(homeApi.getV2HomeSummary).mockResolvedValue(summary); });
  it("renders four clickable today cards and the global sections", async () => { mount(); expect(await screen.findByRole("heading", { name: "Inicio" })).toBeInTheDocument(); expect(screen.getByRole("link", { name: /Tareas\s*1/ })).toHaveAttribute("href", "/seguimiento/tareas"); expect(screen.getByRole("link", { name: /Pendientes\s*2/ })).toBeInTheDocument(); expect(screen.getByRole("link", { name: /Etapas\s*3/ })).toBeInTheDocument(); expect(screen.getByRole("link", { name: /Actividades\s*4/ })).toBeInTheDocument(); expect(screen.getByRole("heading", { name: "Próximas Actividades" })).toBeInTheDocument(); expect(screen.getByRole("heading", { name: "Requieren atención" })).toBeInTheDocument(); expect(screen.getByRole("heading", { name: "Próximos días" })).toBeInTheDocument(); });
  it("renders activity, attention navigation, workspace indicators and seven days", async () => { mount(); expect(await screen.findByRole("link", { name: /Consulta/ })).toHaveTextContent("Personal"); expect(screen.getByRole("link", { name: /Mudanza · Empacar/ })).toHaveAttribute("href", "/seguimiento/proyectos/project-a/etapas/stage-a"); expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(7); });
  it("renders useful empty states", async () => { vi.mocked(homeApi.getV2HomeSummary).mockResolvedValue({ ...summary, upcoming_activities: [], attention: [] }); mount(); expect(await screen.findByText("No hay Actividades próximas.")).toBeInTheDocument(); expect(screen.getByText("Nada requiere atención.")).toBeInTheDocument(); });
  it("renders loading and recoverable error states", async () => { vi.mocked(homeApi.getV2HomeSummary).mockReturnValueOnce(new Promise(() => undefined)); const first = mount(); expect(screen.getByRole("status")).toHaveTextContent("Cargando Inicio"); first.unmount(); vi.mocked(homeApi.getV2HomeSummary).mockRejectedValueOnce(new Error("private")); mount(); expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar Inicio"); });
  it("retries a failed request", async () => { vi.mocked(homeApi.getV2HomeSummary).mockRejectedValueOnce(new Error("private")).mockResolvedValueOnce(summary); mount(); await userEvent.click(await screen.findByRole("button", { name: "Reintentar" })); expect(await screen.findByRole("heading", { name: "Hoy" })).toBeInTheDocument(); });
});
