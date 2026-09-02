import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../../api/authApi";
import { useAuth } from "../../hooks/useAuth";
import { SecuritySettings } from "./SecuritySettings";

vi.mock("../../api/authApi", () => ({ changePassword: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const clearSession = vi.fn();

function LoginDestination() {
  const location = useLocation();
  return <p>{(location.state as { passwordChanged?: boolean } | null)?.passwordChanged ? "Sesión cerrada con confirmación" : "Sin confirmación"}</p>;
}

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><MemoryRouter initialEntries={["/configuracion"]}><Routes><Route path="/configuracion" element={<SecuritySettings />} /><Route path="/login" element={<LoginDestination />} /></Routes></MemoryRouter></QueryClientProvider>);
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Contraseña actual"), "CurrentPassword!");
  await user.type(screen.getByLabelText("Contraseña nueva"), "NewPassword!");
  await user.type(screen.getByLabelText("Confirmar contraseña nueva"), "NewPassword!");
}

describe("SecuritySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ clearSession } as never);
    vi.mocked(authApi.changePassword).mockResolvedValue(undefined);
  });

  it("validates the central policy and confirmation before calling the API", async () => {
    const user = userEvent.setup(); mount();
    await user.type(screen.getByLabelText("Contraseña actual"), "CurrentPassword!");
    await user.type(screen.getByLabelText("Contraseña nueva"), "weak");
    await user.type(screen.getByLabelText("Confirmar contraseña nueva"), "different");
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("al menos 8 caracteres");
    expect(authApi.changePassword).not.toHaveBeenCalled();
  });

  it("changes the password, clears sensitive session state and requires login", async () => {
    const user = userEvent.setup(); mount(); await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    await waitFor(() => expect(authApi.changePassword).toHaveBeenCalled());
    expect(vi.mocked(authApi.changePassword).mock.calls[0][0]).toEqual({ current_password: "CurrentPassword!", new_password: "NewPassword!" });
    expect(clearSession).toHaveBeenCalledOnce();
    expect(await screen.findByText("Sesión cerrada con confirmación")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("CurrentPassword!")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("NewPassword!")).not.toBeInTheDocument();
  });

  it("preserves inputs after a safe recoverable current-password error", async () => {
    vi.mocked(authApi.changePassword).mockRejectedValue({ isAxiosError: true, response: { data: { error: { code: "CURRENT_PASSWORD_INCORRECT" } } } });
    const user = userEvent.setup(); mount(); await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La contraseña actual no es correcta.");
    expect(screen.getByLabelText("Contraseña actual")).toHaveValue("CurrentPassword!");
    expect(screen.getByRole("button", { name: "Cambiar contraseña" })).toBeEnabled();
  });
});
