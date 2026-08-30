import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/v2NotificationApi";
import { useAuth } from "../../hooks/useAuth";
import { testUser } from "../../test/testUser";
import { NotificationSettings } from "./NotificationSettings";

vi.mock("../../api/v2NotificationApi", () => ({ getNotificationPreferences: vi.fn(), updateNotificationPreferences: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));
const preferences = { daily_summary: { enabled: true, local_time: "07:00:00", weekday: null, lock_version: 1 }, daily_review: { enabled: true, local_time: "21:00:00", weekday: null, lock_version: 1 }, pending_weekly: { enabled: true, local_time: "22:00:00", weekday: 6, lock_version: 1 }, project_weekly: { enabled: true, local_time: "22:30:00", weekday: 6, lock_version: 1 }, activity_reminders: { enabled: true, lock_version: 1 } };
function mount() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><NotificationSettings /></QueryClientProvider>); }
describe("NotificationSettings", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(useAuth).mockReturnValue({ user: testUser } as never); vi.mocked(api.getNotificationPreferences).mockResolvedValue(preferences); vi.mocked(api.updateNotificationPreferences).mockResolvedValue(preferences); Object.defineProperty(globalThis, "Notification", { configurable: true, value: { permission: "default", requestPermission: vi.fn().mockResolvedValue("granted") } }); });
  it("loads defaults and saves explicit independent controls", async () => { const user = userEvent.setup(); mount(); const times = await screen.findAllByLabelText("Hora", { selector: "input" }); expect(times[0]).toHaveValue("07:00"); const toggles = screen.getAllByRole("checkbox"); await user.click(toggles[0]); expect(times[0]).toBeDisabled(); await user.click(screen.getByRole("button", { name: "Guardar notificaciones" })); await waitFor(() => expect(api.updateNotificationPreferences).toHaveBeenCalled()); expect(vi.mocked(api.updateNotificationPreferences).mock.calls[0][0].daily_summary.enabled).toBe(false); });
  it("requests browser permission only after an explicit gesture", async () => { const user = userEvent.setup(); mount(); expect(await screen.findByText(/Aún no solicitadas/)).toBeInTheDocument(); expect(Notification.requestPermission).not.toHaveBeenCalled(); await user.click(screen.getByRole("button", { name: "Permitir notificaciones" })); expect(Notification.requestPermission).toHaveBeenCalledOnce(); expect(await screen.findByText(/Permitidas/)).toBeInTheDocument(); });
  it("shows unsupported and recoverable API states safely", async () => { Object.defineProperty(globalThis, "Notification", { configurable: true, value: undefined }); vi.mocked(api.getNotificationPreferences).mockRejectedValueOnce(new Error("private")); mount(); expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar"); });
});
