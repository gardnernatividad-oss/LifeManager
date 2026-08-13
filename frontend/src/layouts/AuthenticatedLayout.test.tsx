import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../hooks/useAuth";
import type { AuthState } from "../store/auth-context";
import { testUser } from "../test/testUser";
import { AuthenticatedLayout } from "./AuthenticatedLayout";

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));

function setMobileViewport(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches,
    media: "(max-width: 48rem)",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  }));
}

function authenticatedState(logout = vi.fn()): AuthState {
  return {
    accessToken: "access-token",
    user: testUser,
    workspace: null,
    isAuthenticated: true,
    isInitializing: false,
    login: vi.fn(),
    logout,
    setWorkspace: vi.fn(),
    clearSession: vi.fn()
  };
}

function renderLayout(initialEntry = "/inicio") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<AuthenticatedLayout />}>
          <Route path="/inicio" element={<h1>Contenido de Inicio</h1>} />
          <Route path="/planificacion/tareas" element={<h1>Contenido de Planificación</h1>} />
        </Route>
        <Route path="/login" element={<h1>Destino de inicio de sesión</h1>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AuthenticatedLayout V1", () => {
  beforeEach(() => {
    setMobileViewport(false);
    vi.mocked(useAuth).mockReturnValue(authenticatedState());
  });

  it("renders the target shell without Workspace selection", () => {
    renderLayout();
    expect(screen.getByRole("navigation", { name: "Secciones de LifeManager" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Contenido de Inicio" })).toBeInTheDocument();
    expect(screen.queryByText(/Espacio de trabajo|Sin espacio|Cambiar espacio/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("renders exact top-level entries and exact nested menus", () => {
    renderLayout("/planificacion/tareas");
    const navigation = screen.getByRole("navigation", { name: "Secciones de LifeManager" });
    expect(within(navigation).getByRole("link", { name: "Inicio" })).toBeInTheDocument();
    expect(within(navigation).getByRole("link", { name: "Revisión" })).toBeInTheDocument();
    expect(within(navigation).getByText("Planificación")).toBeInTheDocument();
    expect(within(navigation).getByText("Seguimiento")).toBeInTheDocument();
    expect(within(navigation).getByText("Reportes")).toBeInTheDocument();
    expect(within(navigation).getByText("Tablas")).toBeInTheDocument();
    expect(within(navigation).getByRole("link", { name: "Configuración" })).toBeInTheDocument();

    const groups = navigation.querySelectorAll("details");
    expect(groups).toHaveLength(4);
    expect(within(groups[0]).getAllByRole("link").map((item) => item.textContent)).toEqual(["Tareas", "Pendientes", "Proyectos"]);
    expect(within(groups[1]).getAllByRole("link").map((item) => item.textContent)).toEqual(["Tareas", "Pendientes", "Proyectos"]);
    expect(within(groups[2]).getAllByRole("link").map((item) => item.textContent)).toEqual(["Tareas", "Pendientes", "Proyectos"]);
    expect(within(groups[3]).getAllByRole("link").map((item) => item.textContent)).toEqual(["Tareas", "Categorías"]);
  });

  it("highlights the active nested navigation item and excludes legacy labels", () => {
    renderLayout("/planificacion/tareas");
    const active = screen.getByRole("link", { name: "Tareas", current: "page" });
    expect(active).toHaveClass("sidebar__sublink--active");
    for (const label of ["Dashboard", "Tareas recurrentes", "Daily Workflow", "Daily Form", "Workspaces", "Settings"]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it("expands a nested navigation section on demand", async () => {
    const user = userEvent.setup();
    renderLayout();
    const planning = screen.getByText("Planificación").closest("details");
    expect(planning).not.toHaveAttribute("open");
    await user.click(screen.getByText("Planificación"));
    expect(planning).toHaveAttribute("open");
  });

  it("renders the current user and logs out to Login", async () => {
    const logout = vi.fn();
    vi.mocked(useAuth).mockReturnValue(authenticatedState(logout));
    const user = userEvent.setup();
    renderLayout();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(logout).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "Destino de inicio de sesión" })).toBeInTheDocument();
  });

  it("opens and closes the mobile sidebar with focus management", async () => {
    setMobileViewport(true);
    const user = userEvent.setup();
    renderLayout();
    const menuButton = await screen.findByRole("button", { name: "Abrir menú de navegación" });
    await user.click(menuButton);
    const sidebar = screen.getByLabelText("Navegación principal");
    const closeButtons = screen.getAllByRole("button", { name: "Cerrar menú de navegación" });
    expect(sidebar).toHaveClass("sidebar--open");
    expect(closeButtons[0]).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(sidebar).not.toHaveClass("sidebar--open"));
    expect(menuButton).toHaveFocus();
  });
});
