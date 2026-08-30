import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import * as activityApi from "../../api/v2ActivityApi";
import * as calendarApi from "../../api/v2CalendarApi";
import { MyCalendarPage } from "./MyCalendarPage";
import { calendarRange, localCalendarDate } from "../../utils/calendarRange";
import { localDateTimeToIso } from "../../utils/taskDateTime";

vi.mock("../../api/v2CalendarApi", () => ({ getMyCalendar: vi.fn() }));
vi.mock("../../api/v2ActivityApi", () => ({ deleteV2Activity: vi.fn(), leaveV2Activity: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ user: { id: "user-1", timezone: "America/Lima" }, workspace: { id: "selected-but-irrelevant" } }) }));
vi.mock("../../hooks/useWorkspaces", () => ({ useWorkspaces: () => ({ data: [{ id: "workspace-a", name: "Familia", kind: "SHARED", lifecycle: "ACTIVE" }] }) }));
let item: ReturnType<typeof calendarItem>;
function calendarItem() { const today = localCalendarDate(new Date(), "America/Lima"); return { activity_id: "activity-1", workspace: { id: "workspace-a", name: "Familia", kind: "SHARED" as const, color: "BLUE" as const, icon: "USERS" as const }, activity_name: "Reunión", category_name: "Familia", starts_at: localDateTimeToIso(`${today}T10:00`, "America/Lima"), ends_at: localDateTimeToIso(`${today}T11:00`, "America/Lima"), organizer: { user_id: "user-2", display_name: "Luis", email: "luis@test.local" }, participants: [{ user_id: "user-1", display_name: "Ana", email: "ana@test.local" }], status: "SCHEDULED" as const, temporal_state: "FUTURE" as const, lock_version: 1, can_edit: true, can_delete: true, can_leave_participation: true }; }
function mount(mobile = false, entry = "/calendario") { window.matchMedia = vi.fn().mockReturnValue({ matches: mobile, addEventListener: vi.fn(), removeEventListener: vi.fn() }); const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}><MyCalendarPage /></QueryClientProvider></MemoryRouter>); }

describe("MyCalendarPage", () => {
  beforeEach(() => { vi.clearAllMocks(); item = calendarItem(); vi.mocked(calendarApi.getMyCalendar).mockResolvedValue({ items: [item] }); vi.mocked(activityApi.deleteV2Activity).mockResolvedValue(); vi.mocked(activityApi.leaveV2Activity).mockResolvedValue(item as never); });
  it("offers a separate calendar comparison route", () => { mount(); expect(screen.getByRole("link", { name: "Comparar" })).toHaveAttribute("href", "/calendario/comparar"); });
  it("defaults to desktop week, Monday start and consolidates Workspace-labelled Activities", async () => {
    const user = userEvent.setup(); mount(); expect(screen.getByRole("button", { name: "Semana" })).toHaveAttribute("aria-pressed", "true"); expect(await screen.findByText("Reunión")).toBeInTheDocument(); expect(screen.getAllByText("Familia").length).toBeGreaterThan(0); const today = localCalendarDate(new Date(), "America/Lima"); const range = calendarRange(today, "WEEK", "America/Lima"); expect(calendarApi.getMyCalendar).toHaveBeenCalledWith(range.from, range.to, "DETAIL", undefined); await user.click(screen.getByText("Reunión")); expect(screen.getByRole("dialog")).toHaveTextContent("Organizador: Luis"); await user.click(screen.getByRole("button", { name: "Eliminar" })); await waitFor(() => expect(activityApi.deleteV2Activity).toHaveBeenCalledWith("workspace-a", "activity-1", 1));
  });
  it("renders untimed summaries and opens a monthly aggregate day", async () => {
    const today = localCalendarDate(new Date(), "America/Lima");
    vi.mocked(calendarApi.getMyCalendar).mockResolvedValue({ items: [], tasks: [{ id: "t", workspace: item.workspace, name: "Comprar", planned_date: today }], pending_items: [], project_stages: [], daily_counts: [] });
    const user = userEvent.setup(); mount(true); expect(await screen.findByText("Comprar")).toBeInTheDocument();
    vi.mocked(calendarApi.getMyCalendar).mockResolvedValue({ items: [], daily_counts: [{ date: today, activities: 2, tasks: 3, pending_items: 1, project_stages: 1 }] });
    await user.click(screen.getByRole("button", { name: "Mes" })); expect(await screen.findByText("2 actividades")).toBeInTheDocument();
    await user.click(screen.getByText("2 actividades").closest("button")!); expect(screen.getByRole("button", { name: "Día" })).toHaveAttribute("aria-pressed", "true");
  });
  it("defaults to mobile day and supports navigation/view controls", async () => {
    const user = userEvent.setup(); mount(true); expect(screen.getByRole("button", { name: "Día" })).toHaveAttribute("aria-pressed", "true"); await user.click(screen.getByRole("button", { name: "Periodo siguiente" })); await waitFor(() => expect(vi.mocked(calendarApi.getMyCalendar).mock.calls.length).toBeGreaterThanOrEqual(2)); await user.click(screen.getByRole("button", { name: "Semana" })); expect(screen.getByRole("button", { name: "Semana" })).toHaveAttribute("aria-pressed", "true");
  });
  it("consumes Home date and Activity navigation context", async () => {
    const requestedDate = localCalendarDate(new Date(item.starts_at), "America/Lima");
    mount(false, `/calendario?date=${requestedDate}&activity=activity-1`);
    expect(screen.getByRole("button", { name: "Día" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("dialog")).toHaveTextContent("Reunión");
    const requestedRange = calendarRange(requestedDate, "DAY", "America/Lima");
    expect(calendarApi.getMyCalendar).toHaveBeenCalledWith(requestedRange.from, requestedRange.to, "DETAIL", undefined);
  });
  it("renders loading, error retry and empty states safely", async () => {
    vi.mocked(calendarApi.getMyCalendar).mockRejectedValueOnce(new Error("private")); const user = userEvent.setup(); mount(); expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar"); vi.mocked(calendarApi.getMyCalendar).mockResolvedValueOnce({ items: [] }); await user.click(screen.getByRole("button", { name: "Reintentar" })); expect(await screen.findByText("No hay elementos en este periodo.")).toBeInTheDocument();
  });
});
