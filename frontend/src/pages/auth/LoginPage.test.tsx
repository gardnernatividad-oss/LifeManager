import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../../hooks/useAuth";
import type { AuthState } from "../../store/auth-context";
import { LoginPage } from "./LoginPage";

vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

function authState(login: AuthState["login"]): AuthState {
  return {
    user: null,
    workspace: null,
    isAuthenticated: false,
    isInitializing: false,
    login,
    logout: vi.fn(),
    setWorkspace: vi.fn(),
    clearSession: vi.fn(),
    setAuthenticatedUser: vi.fn()
  };
}

function renderLogin(initialEntry: string | { pathname: string; state: unknown } = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/inicio" element={<span>Inicio destination</span>} />
        <Route path="/revision" element={<span>Review destination</span>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReset();
  });

  it("links new users to Registration without a page reload", () => {
    vi.mocked(useAuth).mockReturnValue(authState(vi.fn()));
    renderLogin();
    expect(screen.getByRole("link", { name: "Crear cuenta" })).toHaveAttribute("href", "/registro");
  });

  it("validates email and password before submitting", async () => {
    const login = vi.fn();
    vi.mocked(useAuth).mockReturnValue(authState(login));
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Ingresa un correo válido.")).toBeInTheDocument();
    expect(screen.getByText("Ingresa tu contraseña.")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("shows invalid credentials without exposing password or token", async () => {
    const login = vi.fn().mockRejectedValue({
      isAxiosError: true,
      response: { status: 401 }
    });
    vi.mocked(useAuth).mockReturnValue(authState(login));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "plain-secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Credenciales incorrectas.");
    expect(screen.getByLabelText("Correo electrónico")).toHaveValue("ada@example.com");
    expect(screen.getByLabelText("Contraseña")).toHaveValue("");
    expect(screen.queryByText("plain-secret")).not.toBeInTheDocument();
  });

  it("distinguishes a backend connection failure", async () => {
    vi.mocked(useAuth).mockReturnValue(authState(vi.fn().mockRejectedValue(new Error("offline"))));
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos conectar con LifeManager. Intenta nuevamente."
    );
  });

  it("redirects successful login to Inicio", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue(authState(login));
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Inicio destination")).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith({ email: "ada@example.com", password: "secret" });
  });

  it("returns to the attempted protected route after login", async () => {
    vi.mocked(useAuth).mockReturnValue(authState(vi.fn().mockResolvedValue(undefined)));
    const user = userEvent.setup();
    renderLogin({ pathname: "/login", state: { from: { pathname: "/revision" } } });
    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Review destination")).toBeInTheDocument();
  });

  it("disables submission while login is pending", async () => {
    let resolveLogin: (() => void) | undefined;
    const login = vi.fn(() => new Promise<void>((resolve) => { resolveLogin = resolve; }));
    vi.mocked(useAuth).mockReturnValue(authState(login));
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(screen.getByRole("button", { name: "Ingresando…" })).toBeDisabled();
    resolveLogin?.();
    await waitFor(() => expect(screen.getByText("Inicio destination")).toBeInTheDocument());
  });

  it("shows registration success feedback", () => {
    vi.mocked(useAuth).mockReturnValue(authState(vi.fn()));
    renderLogin({ pathname: "/login", state: { registrationSuccess: true } });
    expect(screen.getByRole("status")).toHaveTextContent("Cuenta creada. Ya puedes iniciar sesión.");
  });

  it("confirms a successful authenticated password change", () => {
    vi.mocked(useAuth).mockReturnValue(authState(vi.fn()));
    renderLogin({ pathname: "/login", state: { passwordChanged: true } });
    expect(screen.getByRole("status")).toHaveTextContent("Contraseña actualizada. Inicia sesión nuevamente.");
  });
});
