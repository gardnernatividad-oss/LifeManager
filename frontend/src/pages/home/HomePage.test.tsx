import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as homeApi from "../../api/homeApi";
import { AuthContext, type AuthState } from "../../store/auth-context";
import { testUser } from "../../test/testUser";
import type { HomeSummary } from "../../types/home";
import { HomePage } from "./HomePage";

vi.mock("../../api/homeApi", () => ({ getHomeSummary: vi.fn() }));

const summary: HomeSummary = {
  user_first_name: "Ana",
  local_date: "2026-08-13",
  tasks: { due_today: 2, overdue: 3 },
  pending_items: { overdue: 4 },
  project_steps: { overdue: 5 },
  last_review_saved_at: "2026-08-13T02:30:00Z",
  pending_items_last_tracking_saved_at: "2026-08-12T18:15:00Z"
};

const authState: AuthState = {
  accessToken: "token",
  user: testUser,
  workspace: null,
  isAuthenticated: true,
  isInitializing: false,
  login: vi.fn(),
  logout: vi.fn(),
  setWorkspace: vi.fn(),
  clearSession: vi.fn()
};

function renderHome() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authState}>
        <HomePage />
      </AuthContext.Provider>
    </QueryClientProvider>
  );
  return queryClient;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(homeApi.getHomeSummary).mockResolvedValue(summary);
  });

  it("renders the backend welcome, authoritative date and operational counts", async () => {
    renderHome();
    expect(await screen.findByRole("heading", { name: "Bienvenido a LifeManager, Ana" })).toBeInTheDocument();
    expect(screen.getByText("Hoy, 13 de agosto de 2026")).toBeInTheDocument();
    for (const [label, count] of [
      ["Tareas para hoy", "2"],
      ["Tareas vencidas", "3"],
      ["Pendientes vencidos", "4"],
      ["Pasos vencidos", "5"]
    ]) {
      const card = screen.getByText(label).closest("article");
      expect(card).toHaveTextContent(count);
    }
  });

  it("renders timestamps in the authenticated user's timezone", async () => {
    renderHome();
    await screen.findByRole("heading", { name: "Bienvenido a LifeManager, Ana" });
    const updates = screen.getByLabelText("Últimas actualizaciones");
    expect(updates).toHaveTextContent("Última revisión");
    expect(updates).toHaveTextContent(/12 ago\. 2026.*9:30 p\. m\./i);
    expect(updates).toHaveTextContent("Última actualización de pendientes");
  });

  it("shows real zeros and a neutral overdue state", async () => {
    vi.mocked(homeApi.getHomeSummary).mockResolvedValue({
      ...summary,
      tasks: { due_today: 0, overdue: 0 },
      pending_items: { overdue: 0 },
      project_steps: { overdue: 0 },
      last_review_saved_at: null,
      pending_items_last_tracking_saved_at: null
    });
    renderHome();
    await screen.findByRole("heading", { name: "Bienvenido a LifeManager, Ana" });
    expect(screen.getAllByText("0")).toHaveLength(4);
    expect(screen.getByText("No hay elementos vencidos.")).toBeInTheDocument();
    expect(screen.getAllByText("Sin registro")).toHaveLength(2);
  });

  it("has no quick-access navigation or legacy Dashboard wording", async () => {
    renderHome();
    await screen.findByRole("heading", { name: "Bienvenido a LifeManager, Ana" });
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(/Dashboard|Ir a tareas|Abrir revisión|Ver reportes/i)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("keeps previous data visible while refreshing only Home", async () => {
    const refresh = deferred<HomeSummary>();
    vi.mocked(homeApi.getHomeSummary)
      .mockResolvedValueOnce(summary)
      .mockReturnValueOnce(refresh.promise);
    const user = userEvent.setup();
    const queryClient = renderHome();
    const unrelated = vi.fn();
    queryClient.setQueryData(["unrelated"], { preserved: true });
    expect(await screen.findByText("Tareas para hoy")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Actualizar Inicio" }));
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Actualizando información…");
    expect(queryClient.getQueryData(["unrelated"])).toEqual({ preserved: true });
    expect(unrelated).not.toHaveBeenCalled();
    expect(homeApi.getHomeSummary).toHaveBeenCalledTimes(2);
    refresh.resolve(summary);
    await waitFor(() => expect(screen.getByRole("button", { name: "Actualizar Inicio" })).toBeEnabled());
  });

  it("renders a stable loading state without fake counts", () => {
    vi.mocked(homeApi.getHomeSummary).mockReturnValue(new Promise(() => undefined));
    renderHome();
    expect(screen.getByRole("status", { name: "Cargando Inicio" })).toBeInTheDocument();
    expect(screen.queryByText("Tareas para hoy")).not.toBeInTheDocument();
  });

  it("shows a safe error and retries without fake data", async () => {
    vi.mocked(homeApi.getHomeSummary)
      .mockRejectedValueOnce(new Error("network details"))
      .mockResolvedValueOnce(summary);
    const user = userEvent.setup();
    renderHome();
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar la información de Inicio.");
    expect(screen.queryByText("Tareas para hoy")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Bienvenido a LifeManager, Ana" })).toBeInTheDocument();
    expect(homeApi.getHomeSummary).toHaveBeenCalledTimes(2);
  });
});
