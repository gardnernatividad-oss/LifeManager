import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../../api/authApi";
import { RegistrationPage } from "./RegistrationPage";

vi.mock("../../api/authApi", () => ({ registerUser: vi.fn() }));

function mount() {
  render(<MemoryRouter initialEntries={["/registro"]}><Routes>
    <Route path="/registro" element={<RegistrationPage />} />
    <Route path="/login" element={<p>Login con registro exitoso</p>} />
  </Routes></MemoryRouter>);
}

async function fillValid() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), " Ada ");
  await user.type(screen.getByLabelText("Apellido"), " Lovelace ");
  await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
  await user.type(screen.getByLabelText("Contraseña"), "secret");
  await user.type(screen.getByLabelText("Confirmar contraseña"), "secret");
  return user;
}

describe("RegistrationPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows only the five final registration fields", () => {
    mount();
    for (const label of ["Nombre", "Apellido", "Correo electrónico", "Contraseña", "Confirmar contraseña"])
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    expect(screen.queryByLabelText(/usuario|zona horaria|workspace|espacio|idioma/i)).not.toBeInTheDocument();
  });

  it("validates required values and password confirmation locally", async () => {
    const user = userEvent.setup(); mount();
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(await screen.findByText("Ingresa tu nombre.")).toBeInTheDocument();
    expect(authApi.registerUser).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Nombre"), "Ada");
    await user.type(screen.getByLabelText("Apellido"), "Lovelace");
    await user.type(screen.getByLabelText("Correo electrónico"), "ada@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.type(screen.getByLabelText("Confirmar contraseña"), "different");
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(await screen.findByText("Las contraseñas no coinciden.")).toBeInTheDocument();
  });

  it("submits the exact payload and redirects to Login", async () => {
    vi.mocked(authApi.registerUser).mockResolvedValue();
    mount(); const user = await fillValid();
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    await waitFor(() => expect(authApi.registerUser).toHaveBeenCalledWith({ email: "ada@example.com", password: "secret", first_name: "Ada", last_name: "Lovelace" }));
    expect(await screen.findByText("Login con registro exitoso")).toBeInTheDocument();
  });

  it("shows the safe duplicate-email message for 409", async () => {
    vi.mocked(authApi.registerUser).mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
    mount(); const user = await fillValid();
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ya existe una cuenta con ese correo electrónico.");
  });
});
