import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { listTrackingPendingItems, saveTrackingPendingItems } from "./trackingPendingItemApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));

describe("trackingPendingItemApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the exact list endpoint and does not send workspace_id", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} });
    const params = { page: 1, page_size: 25, is_active: true };
    await listTrackingPendingItems(params);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/pending-items", { params });
    expect(params).not.toHaveProperty("workspace_id");
  });

  it("sends one exact batch with changed fields and lock versions", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const items = [{ id: "one", progress: 25, lock_version: 3 }, { id: "two", comment: "Avance", lock_version: 7 }];
    await saveTrackingPendingItems(items);
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:8000/api/v1/pending-items/tracking", { items });
    expect(vi.mocked(apiClient.patch).mock.calls[0][1]).not.toHaveProperty("workspace_id");
  });
});
