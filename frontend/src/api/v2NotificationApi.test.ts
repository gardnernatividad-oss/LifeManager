import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { getNotificationPreferences, registerPushSubscription, unregisterPushSubscription, updateNotificationPreferences } from "./v2NotificationApi";
vi.mock("./client", () => ({ apiClient: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
describe("v2NotificationApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("maps preferences and own push contracts to canonical absolute V2 URLs", async () => { const data = { daily_summary: {} }; vi.mocked(apiClient.get).mockResolvedValue({ data }); vi.mocked(apiClient.put).mockResolvedValue({ data }); vi.mocked(apiClient.post).mockResolvedValue({ data: { id: "one", is_active: true } }); await getNotificationPreferences(); await updateNotificationPreferences(data as never); await registerPushSubscription({ endpoint: "https://push.example/device", keys: { p256dh: "p", auth: "a" } }); await unregisterPushSubscription("one"); expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v2/notification-preferences"); expect(apiClient.put).toHaveBeenCalledWith("http://localhost:3000/api/v2/notification-preferences", data); expect(apiClient.post).toHaveBeenCalledWith("http://localhost:3000/api/v2/push-subscriptions", expect.any(Object)); expect(apiClient.delete).toHaveBeenCalledWith("http://localhost:3000/api/v2/push-subscriptions/one"); expect(JSON.stringify([vi.mocked(apiClient.get).mock.calls, vi.mocked(apiClient.put).mock.calls])).not.toContain("/api/v1"); });
});
