import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import * as api from "./trackingTaskApi";
vi.mock("./client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));
describe("trackingTaskApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("uses exact V1 Tracking Task paths and payloads without workspace_id", async () => { vi.mocked(apiClient.get).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} }); const params = { page: 1, page_size: 25, status: "PENDIENTE" as const }; await api.listTrackingTasks(params); expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v1/tasks", { params }); await api.updateTrackingTaskResult("task", "COMPLETED", 3); expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:3000/api/v1/tasks/task/result", { result: "COMPLETED", lock_version: 3 }); expect(vi.mocked(apiClient.patch).mock.calls[0][1]).not.toHaveProperty("workspace_id"); });
});
