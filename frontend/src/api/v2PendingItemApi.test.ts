import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { correctV2PendingItem, listV2PendingItemHistory, updateV2PendingItemProgress } from "./v2PendingItemApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

describe("v2PendingItemApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the workspace and Pending scoped history route", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [] } });
    await listV2PendingItemHistory("workspace-a", "pending-a");
    expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/pending-items/pending-a/history"));
  });

  it("sends one atomic progress and comment payload", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
    await updateV2PendingItemProgress("workspace-a", "pending-a", 60, 4, "Avance");
    expect(apiClient.post).toHaveBeenCalledWith(expect.stringContaining("/pending-a/progress"), { progress: 60, comment: "Avance", lock_version: 4 });
  });

  it("supports comment-only and explicit correction contracts", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
    await updateV2PendingItemProgress("workspace-a", "pending-a", null, 4, "Comentario");
    expect(apiClient.post).toHaveBeenCalledWith(expect.stringContaining("/pending-a/progress"), { comment: "Comentario", lock_version: 4 });
    await correctV2PendingItem("workspace-a", "pending-a", 80, 5, "Corrección");
    expect(apiClient.post).toHaveBeenLastCalledWith(expect.stringContaining("/pending-a/correction"), { progress: 80, comment: "Corrección", lock_version: 5 });
  });
});
