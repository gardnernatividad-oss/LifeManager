import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { createRecurringV2Activities, createV2Activity, deleteV2Activity, leaveV2Activity, listV2Activities, updateV2Activity } from "./v2ActivityApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

describe("v2ActivityApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("uses only Workspace-scoped Activity endpoints", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} });
    await listV2Activities("workspace-a", { page: 1, page_size: 25, participant_user_id: "user-1" });
    expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/activities"), { params: { page: 1, page_size: 25, participant_user_id: "user-1" } });
  });
  it("preserves versioned write contracts", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} }); vi.mocked(apiClient.delete).mockResolvedValue({});
    const create = { activity_master_id: "master-1", organizer_user_id: "user-1", participant_user_ids: ["user-2"], starts_at: "2027-01-01T15:00:00Z", ends_at: "2027-01-01T16:00:00Z" };
    await createV2Activity("workspace-a", create);
    await updateV2Activity("workspace-a", "activity-1", { ends_at: "2027-01-01T17:00:00Z", lock_version: 2 });
    await leaveV2Activity("workspace-a", "activity-1", 3);
    await deleteV2Activity("workspace-a", "activity-1", 4);
    expect(apiClient.post).toHaveBeenNthCalledWith(1, expect.stringContaining("/activities"), create);
    expect(apiClient.patch).toHaveBeenCalledWith(expect.stringContaining("/activities/activity-1"), { ends_at: "2027-01-01T17:00:00Z", lock_version: 2 });
    expect(apiClient.post).toHaveBeenNthCalledWith(2, expect.stringContaining("/leave"), { lock_version: 3, scope: "THIS" });
    expect(apiClient.delete).toHaveBeenCalledWith(expect.stringContaining("/activities/activity-1"), { params: { lock_version: 4, scope: "THIS" } });
  });
  it("uses the recurring Activity endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { created_count: 1, items: [] } });
    const payload = { activity_master_id: "master-1", participant_user_ids: [], start_time: "09:00", end_time: "10:00", timezone: "America/Lima", recurrence: { pattern: "DAILY" as const, date_from: "2027-01-01", date_until: "2027-01-01" } };
    await createRecurringV2Activities("workspace-a", payload);
    expect(apiClient.post).toHaveBeenCalledWith(expect.stringContaining("/activities/recurring"), payload);
  });
});
