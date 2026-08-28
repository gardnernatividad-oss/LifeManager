import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as comparisonApi from "../../api/v2CalendarComparisonApi";
import * as calendarApi from "../../api/v2CalendarApi";
import * as workspaceApi from "../../api/workspaceApi";
import { CalendarComparisonPage } from "./CalendarComparisonPage";

vi.mock("../../api/v2CalendarComparisonApi", () => ({ getCalendarComparison: vi.fn() }));
vi.mock("../../api/v2CalendarApi", () => ({ getMyCalendar: vi.fn() }));
vi.mock("../../api/workspaceApi", () => ({ listWorkspaceMembers: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ user: { id: "viewer", timezone: "America/Lima" } }) }));
vi.mock("../../hooks/useWorkspaces", () => ({ useWorkspaces: () => ({ data: [{ id: "personal", name: "Personal", kind: "PERSONAL", lifecycle: "ACTIVE" }, { id: "shared", name: "Familia", kind: "SHARED", lifecycle: "ACTIVE" }], isError: false, refetch: vi.fn() }) }));

function mount() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<MemoryRouter><QueryClientProvider client={client}><CalendarComparisonPage /></QueryClientProvider></MemoryRouter>); }

describe("CalendarComparisonPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(calendarApi.getMyCalendar).mockResolvedValue({ items: [] });
    vi.mocked(workspaceApi.listWorkspaceMembers).mockResolvedValue([
      { user_id: "viewer", display_name: "Ana", email: "ana@test", role: "Miembro", status: "ACTIVE", joined_at: "", ended_at: null },
      { user_id: "target", display_name: "Luis", email: "luis@test", role: "Miembro", status: "ACTIVE", joined_at: "", ended_at: null },
      { user_id: "left", display_name: "Fuera", email: "left@test", role: "Miembro", status: "LEFT", joined_at: "", ended_at: "" },
    ]);
  });
  async function selectTarget(user: ReturnType<typeof userEvent.setup>) {
    await user.selectOptions(screen.getByLabelText("Workspace compartido"), "shared");
    await waitFor(() => expect(screen.getByRole("option", { name: "Luis" })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "Fuera" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Miembro"), "target");
  }
  it("renders DETAILS read-only with back navigation and no target actions", async () => {
    vi.mocked(comparisonApi.getCalendarComparison).mockResolvedValue({ visibility: "SHOW_DETAILS", detailed_events: [{ activity_name: "Médico", starts_at: "2027-01-01T15:00:00Z", ends_at: "2027-01-01T16:00:00Z", temporal_state: "FUTURE" }] });
    const user = userEvent.setup(); mount(); await selectTarget(user);
    expect(await screen.findByText("Médico")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Atrás" })).toHaveAttribute("href", "/calendario");
    expect(screen.queryByRole("button", { name: /Editar|Eliminar|Retirarme/ })).not.toBeInTheDocument();
  });
  it("renders only opaque busy blocks and handles HIDE as privacy state", async () => {
    vi.mocked(comparisonApi.getCalendarComparison).mockResolvedValueOnce({ visibility: "AVAILABILITY_ONLY", busy_blocks: [{ starts_at: "2027-01-01T15:00:00Z", ends_at: "2027-01-01T17:00:00Z", occupied: true }] });
    const user = userEvent.setup(); const { unmount } = mount(); await selectTarget(user);
    expect(await screen.findByText("Ocupado")).toBeInTheDocument(); expect(screen.queryByText("Médico")).not.toBeInTheDocument();
    unmount(); vi.mocked(comparisonApi.getCalendarComparison).mockResolvedValue({ visibility: "HIDE" }); mount(); await selectTarget(userEvent.setup());
    expect(await screen.findByText("Este usuario no comparte su calendario.")).toBeInTheDocument();
  });
});
