import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as privacyApi from "../../api/v2CalendarComparisonApi";
import * as workspaceApi from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { testUser } from "../../test/testUser";
import { CalendarPrivacySettings } from "./CalendarPrivacySettings";

vi.mock("../../api/workspaceApi", () => ({ listManagedWorkspaces: vi.fn() }));
vi.mock("../../api/v2CalendarComparisonApi", () => ({ getCalendarVisibility: vi.fn(), setCalendarVisibility: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const personal = { id: "11111111-1111-4111-8111-111111111111", name: "Personal", kind: "PERSONAL" as const, lifecycle: "ACTIVE" as const, visible_role: "Propietario" as const, can_manage: false, can_delete: false, timezone: "America/Lima", color: "GREEN" as const, icon: "HOME" as const, lock_version: 1 };
const shared = { ...personal, id: "22222222-2222-4222-8222-222222222222", name: "Familia", kind: "SHARED" as const, visible_role: "Miembro" as const };

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><CalendarPrivacySettings /></QueryClientProvider>);
}

describe("CalendarPrivacySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ user: testUser } as never);
    vi.mocked(workspaceApi.listManagedWorkspaces).mockResolvedValue([personal, shared]);
    vi.mocked(privacyApi.getCalendarVisibility).mockResolvedValue({ visibility: "HIDE", lock_version: 2 });
    vi.mocked(privacyApi.setCalendarVisibility).mockResolvedValue({ visibility: "AVAILABILITY_ONLY", lock_version: 3 });
  });

  it("shows only active Shared memberships and persists all three directional values", async () => {
    const user = userEvent.setup(); mount();
    const control = await screen.findByRole("combobox", { name: "Privacidad de calendario en Familia" });
    expect(control).toHaveValue("HIDE");
    expect(screen.queryByRole("combobox", { name: /Personal/ })).not.toBeInTheDocument();
    await user.selectOptions(control, "AVAILABILITY_ONLY");
    await waitFor(() => expect(privacyApi.setCalendarVisibility).toHaveBeenCalledWith(shared.id, "AVAILABILITY_ONLY", 2));
    expect(await screen.findByText("Privacidad guardada.")).toBeInTheDocument();
  });

  it("renders an empty state and retries the Workspace loader", async () => {
    vi.mocked(workspaceApi.listManagedWorkspaces).mockRejectedValueOnce(new Error()).mockResolvedValueOnce([]);
    const user = userEvent.setup(); mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar los espacios compartidos.");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No perteneces a espacios compartidos activos.")).toBeInTheDocument();
  });

  it("reloads the authoritative value after an optimistic concurrency conflict", async () => {
    const conflict = new axios.AxiosError("conflict", "409", undefined, undefined, { status: 409, statusText: "Conflict", headers: {}, config: {} as never, data: {} });
    vi.mocked(privacyApi.setCalendarVisibility).mockRejectedValueOnce(conflict);
    vi.mocked(privacyApi.getCalendarVisibility).mockResolvedValueOnce({ visibility: "HIDE", lock_version: 2 }).mockResolvedValueOnce({ visibility: "SHOW_DETAILS", lock_version: 3 });
    const user = userEvent.setup(); mount();
    const control = await screen.findByRole("combobox", { name: "Privacidad de calendario en Familia" });
    await user.selectOptions(control, "AVAILABILITY_ONLY");
    expect(await screen.findByRole("alert")).toHaveTextContent("La preferencia cambió");
    await waitFor(() => expect(control).toHaveValue("SHOW_DETAILS"));
  });
});
