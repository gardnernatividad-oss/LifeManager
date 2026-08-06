import { render, screen, waitFor } from "@testing-library/react";
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

function renderLayout(initialEntry = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<AuthenticatedLayout />}>
          <Route path="/dashboard" element={<h1>Dashboard content</h1>} />
          <Route path="/tasks" element={<h1>Tasks content</h1>} />
          <Route path="/tasks/recurring" element={<h1>Recurring content</h1>} />
        </Route>
        <Route path="/login" element={<h1>Login destination</h1>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AuthenticatedLayout", () => {
  beforeEach(() => {
    setMobileViewport(false);
    vi.mocked(useAuth).mockReturnValue(authenticatedState());
  });

  it("renders the application shell and protected route outlet", () => {
    renderLayout();

    expect(screen.getByRole("navigation", { name: "Secciones de LifeManager" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dashboard content" })).toBeInTheDocument();
    expect(screen.getByText("Personal")).toBeInTheDocument();
  });

  it("highlights only the active navigation item", () => {
    renderLayout("/tasks/recurring");

    expect(screen.getByRole("link", { name: "Recurring Tasks" })).toHaveClass("sidebar__link--active");
    expect(screen.getByRole("link", { name: "Tasks" })).not.toHaveClass("sidebar__link--active");
  });

  it("renders the current user's full name and email", () => {
    renderLayout();

    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("logs out through the auth context and navigates to Login", async () => {
    const logout = vi.fn();
    vi.mocked(useAuth).mockReturnValue(authenticatedState(logout));
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(logout).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "Login destination" })).toBeInTheDocument();
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
