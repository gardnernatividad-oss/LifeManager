import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as adminApi from "../../api/adminApi";
import { AdminPage } from "./AdminPage";

vi.mock("../../api/adminApi");

const request = { id: "r1", email: "pending@example.com", first_name: "Pen", last_name: "Ding", timezone: "America/Lima", account_status: "PENDING_APPROVAL" as const, email_verified_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z" };
const active = { ...request, id: "u1", email: "active@example.com", account_status: "ACTIVE" as const, global_role: null, status_changed_at: request.created_at, lock_version: 1 };

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><AdminPage /></QueryClientProvider>);
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminApi.listAccountRequests).mockResolvedValue({ items: [request], total: 1 });
    vi.mocked(adminApi.listAdminUsers).mockResolvedValue({ items: [active], total: 1, page: 1, page_size: 25, total_pages: 1 });
    vi.mocked(adminApi.approveAccountRequest).mockResolvedValue({ ...request, account_status: "ACTIVE" });
    vi.mocked(adminApi.disableAdminUser).mockResolvedValue({ ...active, account_status: "DISABLED", lock_version: 2 });
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("renders pending requests and minimal paginated users", async () => {
    mount();
    expect(await screen.findByText("pending@example.com")).toBeInTheDocument();
    expect(await screen.findByText("active@example.com")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
  });

  it("approves a request and reports success", async () => {
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: "Aprobar" }));
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(adminApi.approveAccountRequest).toHaveBeenCalledWith("r1"));
    expect(await screen.findByText("Operación completada.")).toBeInTheDocument();
  });

  it("confirms and disables an active ordinary account", async () => {
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: "Deshabilitar" }));
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(adminApi.disableAdminUser).toHaveBeenCalledWith(active));
  });

  it("shows safe recoverable loading errors", async () => {
    vi.mocked(adminApi.listAccountRequests).mockRejectedValue(new Error("private"));
    mount();
    expect(await screen.findByText("No pudimos cargar las solicitudes.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("sends search, status and pagination through the server query", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByText("active@example.com");
    await user.type(screen.getByLabelText("Buscar"), "Ada");
    await user.selectOptions(screen.getByLabelText("Estado"), "DISABLED");
    await waitFor(() => expect(adminApi.listAdminUsers).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 25, search: "Ada", account_status: "DISABLED" })));

    vi.mocked(adminApi.listAdminUsers).mockResolvedValue({ items: [active], total: 26, page: 1, page_size: 25, total_pages: 2 });
    await user.selectOptions(screen.getByLabelText("Estado"), "ACTIVE");
    await screen.findByText("Página 1 de 2");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(adminApi.listAdminUsers).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("shows an empty state and a safe recoverable conflict", async () => {
    vi.mocked(adminApi.listAccountRequests).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(adminApi.disableAdminUser).mockRejectedValue(Object.assign(new Error("conflict"), { isAxiosError: true, response: { status: 409 } }));
    const user = userEvent.setup(); mount();
    expect(await screen.findByText("No hay solicitudes pendientes.")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Deshabilitar" }));
    expect(await screen.findByText(/La cuenta cambió/)).toBeInTheDocument();
    expect(adminApi.listAdminUsers).toHaveBeenCalled();
  });
});
